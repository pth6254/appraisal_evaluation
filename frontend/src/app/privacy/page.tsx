import type { Metadata } from "next";

export const metadata: Metadata = { title: "개인정보처리방침 — 부동산 컨시어지" };

const SECTIONS = [
  {
    title: "1. 수집하는 개인정보 항목",
    body: [
      "회원가입 시: 이메일 주소, 이름(선택), 비밀번호(단방향 암호화 저장). Google 계정으로 가입 시 Google이 제공하는 이메일·이름·프로필 사진 URL.",
      "서비스 이용 과정에서: 시세추정 조회 내역, 권리 점검·상담 이용 기록(아래 최소화 원칙 적용), 접속 로그.",
    ],
  },
  {
    title: "2. 등기부등본 등 업로드 문서의 처리 (중요)",
    body: [
      "권리관계 위험 점검에 업로드한 등기부등본·건축물대장 PDF는 서버 메모리에서만 분석되며, 분석 완료 즉시 파기됩니다. 파일 자체는 디스크·데이터베이스 등 어디에도 저장되지 않습니다.",
      "이용 기록에는 문서의 상세 주소 대신 행정구역 수준으로 마스킹된 주소와 위험 등급만 저장됩니다.",
      "법률·세금 상담 질문은 원문이 저장되지 않으며, 이용 기록에는 질문의 앞부분 일부만 축약 저장됩니다.",
    ],
  },
  {
    title: "3. 개인정보의 이용 목적",
    body: [
      "회원 식별 및 로그인 세션 유지 (JWT 쿠키).",
      "본인의 시세추정 이력·이용 기록 제공 (다른 사용자에게 공개되지 않음).",
      "서비스 남용 방지 (요청 횟수 제한).",
    ],
  },
  {
    title: "4. 보유 기간 및 파기",
    body: [
      "회원 정보와 이용 기록은 회원 탈퇴 시 즉시 삭제됩니다 (복구 불가).",
      "사이드바의 “회원 탈퇴” 기능으로 계정·시세추정 이력·활동 기록 전체를 직접 삭제할 수 있습니다.",
    ],
  },
  {
    title: "5. 제3자 제공 및 외부 서비스",
    body: [
      "개인정보를 제3자에게 판매·제공하지 않습니다.",
      "주소 검색(카카오), 실거래가 조회(국토교통부) 등 외부 API 호출에는 개인 식별 정보가 포함되지 않습니다.",
      "Google 로그인 사용 시 Google의 개인정보처리방침이 함께 적용됩니다.",
    ],
  },
  {
    title: "6. 이용자의 권리",
    body: [
      "본인 정보의 조회·삭제(회원 탈퇴)를 언제든 요청할 수 있습니다.",
      "문의: pth121819@gmail.com",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-extrabold tracking-tight text-ink mb-1">개인정보처리방침</h1>
      <p className="text-xs text-ink-faint mb-6">시행일: 2026년 7월 11일</p>
      <div className="space-y-5">
        {SECTIONS.map(s => (
          <section key={s.title} className="rounded-xl border border-line bg-surface p-5">
            <h2 className="text-sm font-bold text-ink mb-2">{s.title}</h2>
            <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-muted">
              {s.body.map((line, i) => <li key={i}>{line}</li>)}
            </ul>
          </section>
        ))}
      </div>
      <p className="mt-6 pb-4 text-center text-[11.5px] text-ink-faint">
        본 방침은 서비스 개선에 따라 변경될 수 있으며, 변경 시 본 페이지에 게시합니다.
      </p>
    </div>
  );
}
