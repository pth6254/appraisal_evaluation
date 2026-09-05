"""평가기 자체가 잘못된 결과를 통과시키지 않는지 검증한다."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.cli import DATASETS, compare_reports, load_dataset, main
from evaluation.metrics import retrieval_metrics
from evaluation.report import summarize, write_report
from evaluation.runner import run_case
from evaluation.schema import ChatCase, ChatTurn, Dataset, RagCase, equals
from evaluation.suites import calculator, chat, rag


def test_dataset_typos_duplicates_and_empty_gold_are_rejected():
    with pytest.raises(ValidationError):
        RagCase(id="x", question="질문", relevant_title=["정답"])
    with pytest.raises(ValidationError):
        RagCase(id="x", question="질문")
    case = {"id": "same", "question": "질문", "relevant_titles": ["정답"]}
    with pytest.raises(ValueError, match="중복"):
        Dataset(version="1", suite="rag", cases=[case, case]).validated_cases()


def test_rank_metrics_penalize_duplicates_short_results_and_bad_rank():
    metric = retrieval_metrics(["wrong", "A", "A", "B"], ["A", "B"], 4)
    assert metric["precision_at_k"] == 0.5
    assert metric["recall_at_k"] == 1
    assert metric["mrr_at_k"] == 0.5
    assert 0 < metric["ndcg_at_k"] < 1
    assert retrieval_metrics(["A"], ["A"], 4)["precision_at_k"] == 0.25
    assert retrieval_metrics([], [], 4)["recall_at_k"] is None


def test_numeric_comparison_does_not_treat_bool_as_money():
    assert not equals(1, True)
    assert not equals(True, 1)
    assert not equals(1, float("nan"))
    assert equals(100, 101, 1)


@pytest.mark.parametrize("suite", ["calculator", "rag", "chat"])
def test_bundled_datasets_validate(suite):
    dataset, cases = load_dataset(DATASETS / f"{suite}.json")
    assert dataset.suite == suite and cases


def test_calculator_checks_fixed_oracle_and_rule_date():
    _, cases = load_dataset(DATASETS / "calculator.json")
    original = cases[0]
    assert calculator(original)["status"] == "pass"
    wrong = original.model_copy(deep=True)
    wrong.expected["tax"] += 1
    assert calculator(wrong)["status"] == "fail"
    wrong = original.model_copy(deep=True)
    wrong.reference.as_of = "2000-01-01"
    assert calculator(wrong)["status"] == "fail"


def test_seed_search_uses_no_database_and_no_embedding(monkeypatch):
    from backend import chat_corpus
    def forbidden(*args, **kwargs):
        raise AssertionError("오프라인 평가에서 외부 자원 접근")
    monkeypatch.setattr(chat_corpus, "ensure_corpus", forbidden)
    monkeypatch.setattr(chat_corpus, "_try_embed", forbidden)
    case = RagCase(id="gift", question="증여세 공제 세율", relevant_titles=["증여세 공제와 세율"])
    result = rag(case, live=False, k=4)
    assert result["status"] == "pass"
    assert result["details"]["mode"] == "seed_keyword_only"


def test_chat_uses_actual_history_and_detects_wrong_params_and_fallback():
    histories = []
    def answer(question, history, *, trace):
        histories.append(deepcopy(history))
        trace.update(route={"tool": "gift_tax", "params": {"gift_value": 100}},
                     tool_result={"outputs": {"tax": 0}}, fallback="tool")
        return {"answer": "실제 생성된 응답"}
    case = ChatCase(id="multi", turns=[
        ChatTurn(question="첫 질문", expected_tool="gift_tax", expected_params={"gift_value": 200}, review_focus="금액"),
        ChatTurn(question="후속 질문", expected_tool="none", review_focus="맥락"),
    ])
    result = chat(case, answer_fn=answer)
    assert result["status"] == "fail" and result["review_required"]
    assert histories == [[], [{"role": "user", "content": "첫 질문"}, {"role": "assistant", "content": "실제 생성된 응답"}]]
    assert result["metrics"]["fallback_turns"] == 2
    assert not next(c for c in result["checks"] if c["name"] == "turn_1.params.gift_value")["passed"]


def test_correct_tool_output_does_not_hide_wrong_answer_amount():
    def answer(question, history, *, trace):
        trace.update(route={"tool": "gift_tax", "params": {}}, tool_result={"outputs": {"tax": 77600000}})
        return {"answer": "세금은 88,123,456원입니다."}
    case = ChatCase(id="wrong-answer", turns=[ChatTurn(question="질문", expected_tool="gift_tax",
        expected_outputs={"tax": 77600000}, answer_required_numbers=[77600000], review_focus="답변 수치")])
    result = chat(case, answer_fn=answer)
    assert result["status"] == "fail"
    assert not next(c for c in result["checks"] if c["name"] == "turn_1.answer_numbers")["passed"]


def test_report_escapes_generated_html_and_does_not_count_errors_as_pass(tmp_path):
    result = {"suite": "chat", "id": "<script>alert(1)</script>", "repeat": 1, "status": "error",
              "elapsed_seconds": 1, "details": {"answer": "<img src=x onerror=alert(1)>"}, "checks": [], "review_required": True}
    report = write_report(tmp_path / "run", {"run_id": "test"}, [result])
    assert report["summary"]["errors"] == 1 and report["summary"]["pass_rate"] == 0
    content = (tmp_path / "run/report.html").read_text(encoding="utf-8")
    assert "<img src=x" not in content and "<script>alert(1)" not in content
    assert "&lt;script&gt;" in content
    reviews = json.loads((tmp_path / "run/human_review.json").read_text(encoding="utf-8"))
    assert reviews["reviews"][0]["status"] == "pending"


def test_empty_report_has_no_success_rate():
    assert summarize([])["pass_rate"] is None


def test_compare_detects_regression_and_removed_cases(tmp_path):
    before = {"metadata": {"datasets": {"x": "hash"}, "live": False, "k": 4},
              "results": [{"suite": "rag", "id": "a", "repeat": 1, "status": "pass"},
                          {"suite": "rag", "id": "b", "repeat": 1, "status": "pass"}]}
    after = deepcopy(before)
    after["results"] = after["results"][:1]
    after["results"][0]["status"] = "fail"
    for name, data in [("before", before), ("after", after)]:
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    result = compare_reports(tmp_path / "before.json", tmp_path / "after.json")
    assert result["regressions"] == 1 and result["removed"] == [["rag", "b", 1]]


def test_worker_timeout_and_execution_error_are_not_success():
    _, cases = load_dataset(DATASETS / "calculator.json")
    assert run_case("calculator", cases[0], live=False, k=4, timeout=0.001)["details"]["error_type"] == "Timeout"
    broken = cases[0].model_copy(deep=True)
    broken.inputs = {"unknown_input": 1}
    result = run_case("calculator", broken, live=False, k=4, timeout=20)
    assert result["status"] == "error" and result["details"]["error_type"] == "TypeError"


def test_chat_requires_explicit_live_mode():
    with pytest.raises(SystemExit) as error:
        main(["run", "--suite", "chat"])
    assert error.value.code == 2


def test_cli_error_exit_and_report_generation(tmp_path):
    _, cases = load_dataset(DATASETS / "calculator.json")
    broken = cases[0].model_copy(deep=True)
    broken.expected["tax"] = -1
    dataset = tmp_path / "calculator.json"
    dataset.write_text(json.dumps({"version": "1", "suite": "calculator", "cases": [broken.model_dump()]}), encoding="utf-8")
    assert main(["run", "--dataset", str(dataset), "--output", str(tmp_path / "output")]) == 1
    assert len(list((tmp_path / "output").glob("*/results.json"))) == 1


def test_legacy_python_import_is_static_and_preserves_questions(tmp_path):
    from evaluation.legacy import import_rag
    source = tmp_path / "rag_eval.py"
    source.write_text('raise RuntimeError("실행하면 안 됨")\nEVAL_CASES = [{"id": "old-1", "q": "질문", "gold": ["문서"]}]', encoding="utf-8")
    result = import_rag(source, question_key="q", titles_key="gold", variable="EVAL_CASES")
    assert result.cases[0] == {"id": "old-1", "question": "질문", "relevant_titles": ["문서"], "expect_no_results": False}
    source.write_text('EVAL_CASES = make_cases()', encoding="utf-8")
    with pytest.raises(ValueError):
        import_rag(source, question_key="q", titles_key="gold", variable="EVAL_CASES")


def test_legacy_import_does_not_overwrite_existing_dataset(tmp_path):
    source = tmp_path / "old.json"
    source.write_text(json.dumps([{"question": "질문", "relevant_titles": ["문서"]}]), encoding="utf-8")
    destination = tmp_path / "existing.json"
    destination.write_text("original", encoding="utf-8")
    assert main(["import-rag", str(source), str(destination)]) == 2
    assert destination.read_text(encoding="utf-8") == "original"


def test_human_review_requires_complete_matching_coverage():
    from evaluation.review import HumanReview, Reviews, summarize_reviews
    report = {"metadata": {"run_id": "test"}, "results": [{"id": "a", "repeat": 1, "review_required": True}]}
    review = {"id": "a", "repeat": 1, "status": "pending", "scores": {}}
    pending = Reviews(run_id="test", reviews=[HumanReview.model_validate(review)])
    assert summarize_reviews(report, pending)["pending"] == 1
    with pytest.raises(ValueError):
        summarize_reviews(report, Reviews(run_id="test", reviews=[]))
    with pytest.raises(ValidationError):
        HumanReview.model_validate(dict(review, status="reviewed"))
    complete = dict(review, status="reviewed", reviewer="검토자", critical_error=True,
                    scores={"relevance": 5, "groundedness": 5, "context_retention": 5, "clarity": 5})
    summary = summarize_reviews(report, Reviews(run_id="test", reviews=[HumanReview.model_validate(complete)]))
    assert summary["failed"] == 1 and summary["critical_errors"] == 1


def test_chat_streams_active_stage_before_generation_finishes():
    progress = []
    def interrupted(question, history, *, trace):
        trace["stage"] = "generation"
        trace.update(route={"tool": "none", "params": {}})
        raise TimeoutError("중단")
    case = ChatCase(id="partial", turns=[ChatTurn(question="질문", expected_tool="none", review_focus="중단")])
    with pytest.raises(TimeoutError):
        chat(case, answer_fn=interrupted, on_progress=progress.append)
    assert progress[-1]["active_turn"] == 1
    assert progress[-1]["trace"]["stage"] == "generation"
    assert progress[-1]["trace"]["route"]["tool"] == "none"


def test_worker_keeps_progress_message_before_failure(monkeypatch):
    from evaluation import runner
    messages = []
    class Connection:
        def send(self, value):
            messages.append(value)
        def close(self):
            pass
    def execute(*args, on_progress):
        on_progress({"active_turn": 1})
        raise RuntimeError("접속 문자열을 출력하면 안 됨")
    monkeypatch.setattr(runner, "_execute", execute)
    runner._worker(Connection(), "chat", {}, True, 4)
    assert messages == [("progress", {"active_turn": 1}), ("error", "RuntimeError")]
