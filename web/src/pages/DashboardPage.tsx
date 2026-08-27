import { useAuth } from "../auth/AuthContext";
import { HealthBadge, QueryState, SectionCard } from "../components/HealthBadge";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import { UI, formatHealthLabel } from "../utils/uiLabels";

export function DashboardPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: operationsApi.getDashboard,
    refreshMs: getRefreshIntervalMs(),
  });

  if (status !== "success" || !data) {
    return <QueryState status={status} message={errorMessage} onRetry={() => void refresh()} />;
  }

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h2>{UI.dashboard}</h2>
          <p className="muted">
            {UI.generatedAt} {data.generated_at}
          </p>
        </div>
        <HealthBadge label={formatHealthLabel(UI.dashboard)} status={data.summary.health} />
      </div>

      <div className="card-grid">
        <SectionCard title="크롤러" readError={data.crawler.read_error}>
          <ul className="metric-list">
            <li>전체 대상: {data.crawler.total_targets}</li>
            <li>실패: {data.crawler.failed_targets}</li>
            <li>SSG 접근 거부: {data.crawler.ssg_access_denied}</li>
            <li>최근 실패: {data.crawler.recent_failures}</li>
          </ul>
        </SectionCard>
        <SectionCard title="가격" readError={data.price.read_error}>
          <ul className="metric-list">
            <li>대상: {data.price.targets}</li>
            <li>가격 있음: {data.price.with_price}</li>
            <li>이력 없음: {data.price.no_history}</li>
            <li>잘못된 가격: {data.price.invalid_price}</li>
          </ul>
        </SectionCard>
        <SectionCard title="가격 알림" readError={data.alerts.read_error}>
          <ul className="metric-list">
            <li>전체: {data.alerts.total}</li>
            <li>활성: {data.alerts.enabled}</li>
            <li>무효: {data.alerts.invalid}</li>
            <li>최근 무효: {data.alerts.recent_invalid}</li>
          </ul>
        </SectionCard>
        <SectionCard title="알림 전송" readError={data.notifications.read_error}>
          <ul className="metric-list">
            <li>전송 완료: {data.notifications.sent}</li>
            <li>실패: {data.notifications.failed}</li>
            <li>건너뜀: {data.notifications.skipped}</li>
            <li>최근 실패: {data.notifications.recent_failures.length}</li>
          </ul>
        </SectionCard>
        <SectionCard title="실행기" readError={data.runner.read_error}>
          <ul className="metric-list">
            <li>상태: {data.runner.last_cycle_status}</li>
            <li>최근 실행 횟수: {data.runner.recent_cycles}</li>
            <li>실패한 실행 횟수: {data.runner.recent_failed_cycles}</li>
            <li>알림 전송 실패: {data.runner.notification_failed}</li>
          </ul>
        </SectionCard>
        <SectionCard title="감사 로그" readError={data.audit.read_error}>
          <ul className="metric-list">
            <li>최근 이벤트: {data.audit.recent_events}</li>
            <li>최근 실패: {data.audit.recent_failures}</li>
            <li>알림 발생: {data.audit.recent_alert_triggered}</li>
            <li>실행기 실패: {data.audit.recent_runner_failed}</li>
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
