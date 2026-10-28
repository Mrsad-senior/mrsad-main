import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AuditVerifyReport, StatsOverview, TimeseriesPoint } from '../../shared/api/types';
import { useApi, useAuth } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useLiveEvent } from '../../shared/app/live';
import { readCssVars, useTheme } from '../../shared/app/theme';
import { useToast } from '../../shared/app/toast';
import { Icon, type IconName } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { toDate } from '../../shared/lib/format';
import { PageHeader, Section } from '../components/PageHeader';

const RANGES = [
  { hours: 1, bucket: 5, key: 'overview.range1h' },
  { hours: 24, bucket: 60, key: 'overview.range24h' },
  { hours: 24 * 7, bucket: 360, key: 'overview.range7d' },
] as const;

const COLOR_VARS = ['chart-allow', 'chart-approval', 'chart-deny', 'chart-injection', 'chart-accent', 'chart-grid', 'chart-axis', 'surface', 'text', 'border'] as const;
type ChartColors = Record<(typeof COLOR_VARS)[number], string>;

interface OverviewData {
  stats: StatsOverview;
  series: TimeseriesPoint[];
}

export default function Overview() {
  const api = useApi();
  const { t } = useI18n();
  const [rangeIndex, setRangeIndex] = useState(1);
  const range = RANGES[rangeIndex];

  const query = useQuery<OverviewData>(
    async (signal) => {
      const [stats, series] = await Promise.all([
        api.statsOverview(range.hours, signal),
        api.timeseries(range.hours, range.bucket, signal),
      ]);
      return { stats, series };
    },
    [api, range.hours, range.bucket],
  );

  // Live: refresh at most every 5 s while events stream in, and every 30 s regardless.
  const lastRefresh = useRef(0);
  const { reload } = query;
  useLiveEvent(() => {
    const now = Date.now();
    if (now - lastRefresh.current > 5000) {
      lastRefresh.current = now;
      reload();
    }
  });
  useEffect(() => {
    const timer = setInterval(reload, 30_000);
    return () => clearInterval(timer);
  }, [reload]);

  return (
    <div className="stack-lg">
      <PageHeader
        title={t('overview.title')}
        subtitle={t('overview.subtitle')}
        actions={
          <button type="button" className="btn btn--ghost btn--sm" onClick={reload}>
            <Icon name="refresh" size={16} />
            {t('app.refresh')}
          </button>
        }
      />
      <fieldset className="segmented" aria-describedby="range-hint">
        <legend className="visually-hidden">{t('overview.range')}</legend>
        {RANGES.map((r, i) => (
          <label key={r.key} className="segmented__option">
            <input type="radio" name="range" checked={i === rangeIndex} onChange={() => setRangeIndex(i)} />
            <span>{t(r.key)}</span>
          </label>
        ))}
        <span id="range-hint" className="muted small range-hint">
          {t('overview.autoRefresh')}
        </span>
      </fieldset>
      <QueryView {...query}>{(data) => <OverviewBody data={data} bucketMinutes={range.bucket} />}</QueryView>
    </div>
  );
}

function OverviewBody({ data, bucketMinutes }: { data: OverviewData; bucketMinutes: number }) {
  const { t, fmtNumber, fmtPercent, fmtMs } = useI18n();
  const { stats, series } = data;
  const total = stats.total_calls || 0;
  const pct = (n: number) => (total ? t('kpi.ofTotal', { pct: fmtPercent(n / total) }) : undefined);

  const kpis: { label: string; value: string; icon: IconName; tone?: string; note?: string; hero?: boolean }[] = [
    { label: t('kpi.totalCalls'), value: fmtNumber(total), icon: 'activity', hero: true },
    { label: t('kpi.allowed'), value: fmtNumber(stats.allowed), icon: 'check-circle', tone: 'allow', note: pct(stats.allowed) },
    { label: t('kpi.denied'), value: fmtNumber(stats.denied), icon: 'x-octagon', tone: 'deny', note: pct(stats.denied) },
    { label: t('kpi.approvalsRequired'), value: fmtNumber(stats.approvals_required), icon: 'pause', tone: 'warn', note: pct(stats.approvals_required) },
    { label: t('kpi.approvalsPending'), value: fmtNumber(stats.approvals_pending), icon: 'clock', tone: stats.approvals_pending ? 'warn' : undefined },
    { label: t('kpi.injections'), value: fmtNumber(stats.injections_detected), icon: 'shield-alert', tone: stats.injections_detected ? 'deny' : undefined },
    { label: t('kpi.sanitized'), value: fmtNumber(stats.results_sanitized), icon: 'shield-check' },
    ...(stats.results_blocked !== undefined
      ? [{ label: t('kpi.blocked'), value: fmtNumber(stats.results_blocked), icon: 'x-octagon' as IconName, tone: stats.results_blocked ? 'deny' : undefined }]
      : []),
    { label: t('kpi.latencyMedian'), value: fmtMs(stats.median_latency_ms), icon: 'zap', note: t('kpi.latencyNote') },
    { label: t('kpi.latencyP95'), value: fmtMs(stats.p95_latency_ms), icon: 'zap' },
  ];

  return (
    <div className="stack-lg">
      <div className="overview-top">
        <ul className="kpis" aria-label={t('overview.kpis')}>
          {kpis.map((k) => (
            <li key={k.label} className={`kpi${k.tone ? ` kpi--${k.tone}` : ''}${k.hero ? ' kpi--hero' : ''}`}>
              <span className="kpi__label">
                <Icon name={k.icon} size={16} />
                {k.label}
              </span>
              <span className="kpi__value">{k.value}</span>
              {k.note ? <span className="kpi__note">{k.note}</span> : null}
            </li>
          ))}
        </ul>
        <AuditCard initialOk={stats.audit_ok} />
      </div>

      {total === 0 && series.every((p) => !p.allowed && !p.denied && !p.require_approval && !p.injections) ? (
        <div className="card">
          <EmptyState icon="activity" title={t('overview.noData')}>
            <p>{t('overview.noDataHint')}</p>
          </EmptyState>
        </div>
      ) : (
        <>
          <TimeseriesCard series={series} bucketMinutes={bucketMinutes} />
          <div className="grid-2">
            <ByToolCard stats={stats} />
            <ByLayerCard stats={stats} />
          </div>
        </>
      )}
    </div>
  );
}

function AuditCard({ initialOk }: { initialOk: boolean | null }) {
  const api = useApi();
  const toast = useToast();
  const { hasRole } = useAuth();
  const { t, fmtNumber } = useI18n();
  const [report, setReport] = useState<AuditVerifyReport | null>(null);
  const [pending, setPending] = useState(false);
  const ok = report ? report.ok : initialOk;
  const state = ok === true ? 'ok' : ok === false ? 'broken' : 'unknown';

  async function verify() {
    setPending(true);
    try {
      setReport(await api.verifyAudit());
    } catch (err) {
      toast.error(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={`card audit-card audit-card--${state}`} aria-labelledby="audit-title" aria-live="polite">
      <h2 className="card__title" id="audit-title">
        <Icon name="database" size={18} />
        {t('overview.audit')}
      </h2>
      <p className="audit-card__status">
        <Icon name={state === 'ok' ? 'shield-check' : state === 'broken' ? 'shield-alert' : 'shield'} size={28} />
        <span>{t(state === 'ok' ? 'overview.auditOk' : state === 'broken' ? 'overview.auditBroken' : 'overview.auditUnknown')}</span>
      </p>
      {report ? (
        <p className="muted small">
          {report.ok
            ? t('overview.auditChecked', { count: fmtNumber(report.checked) })
            : t('activity.verifyFail', { seq: report.first_bad_seq ?? '?', message: report.message })}
        </p>
      ) : (
        <p className="muted small">{t('overview.auditHint')}</p>
      )}
      {hasRole('admin', 'auditor') ? (
        <button type="button" className="btn btn--ghost btn--sm" onClick={verify} disabled={pending} aria-busy={pending}>
          <Icon name="shield-check" size={16} />
          {t('overview.verifyNow')}
        </button>
      ) : null}
    </section>
  );
}

function useChartColors(): ChartColors {
  const { resolved } = useTheme();
  // `resolved` is the cache key: tokens are re-read whenever the effective theme changes.
  return useMemo(() => readCssVars(COLOR_VARS), [resolved]);
}

function TableToggle({ table, onToggle, controls }: { table: boolean; onToggle: () => void; controls: string }) {
  const { t } = useI18n();
  return (
    <button type="button" className="btn btn--ghost btn--sm" onClick={onToggle} aria-pressed={table} aria-controls={controls}>
      <Icon name={table ? 'activity' : 'grid'} size={16} />
      {table ? t('overview.showChart') : t('overview.showTable')}
    </button>
  );
}

interface SeriesDef {
  key: 'allowed' | 'require_approval' | 'denied' | 'injections';
  color: keyof ChartColors;
  label: string;
}

function TimeseriesCard({ series, bucketMinutes }: { series: TimeseriesPoint[]; bucketMinutes: number }) {
  const { t, fmtNumber, fmtDateTime, dir } = useI18n();
  const colors = useChartColors();
  const [asTable, setAsTable] = useState(false);
  const defs: SeriesDef[] = [
    { key: 'allowed', color: 'chart-allow', label: t('action.allow') },
    { key: 'require_approval', color: 'chart-approval', label: t('action.require_approval') },
    { key: 'denied', color: 'chart-deny', label: t('action.deny') },
    { key: 'injections', color: 'chart-injection', label: t('overview.seriesInjections') },
  ];
  const rows = series.map((p) => ({ ...p, ms: toDate(p.t)?.getTime() ?? 0 }));
  const timeFormat: Intl.DateTimeFormatOptions =
    bucketMinutes >= 360 ? { weekday: 'short', hour: '2-digit' } : bucketMinutes >= 60 ? { hour: '2-digit', minute: '2-digit' } : { hour: '2-digit', minute: '2-digit' };
  const rtl = dir === 'rtl';

  return (
    <Section
      id="ts"
      title={t('overview.timeseries')}
      subtitle={t('overview.timeseriesDesc')}
      actions={<TableToggle table={asTable} onToggle={() => setAsTable((v) => !v)} controls="ts-body" />}
    >
      <div id="ts-body">
        {asTable ? (
          <div className="table-wrap">
            <table className="table table--compact">
              <caption className="visually-hidden">{t('overview.timeseries')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('overview.colTime')}</th>
                  {defs.map((d) => (
                    <th key={d.key} scope="col" className="num">
                      {d.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.ms}>
                    <th scope="row">{fmtDateTime(r.ms, { dateStyle: 'short', timeStyle: 'short' })}</th>
                    {defs.map((d) => (
                      <td key={d.key} className="num">
                        {fmtNumber(r[d.key] ?? 0)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="chart" role="img" aria-label={t('overview.timeseriesAlt')}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={colors['chart-grid']} vertical={false} />
                <XAxis
                  dataKey="ms"
                  type="number"
                  scale="time"
                  domain={['dataMin', 'dataMax']}
                  reversed={rtl}
                  tickFormatter={(v: number) => fmtDateTime(v, timeFormat)}
                  stroke={colors['chart-grid']}
                  tick={{ fill: colors['chart-axis'], fontSize: 12 }}
                  minTickGap={24}
                />
                <YAxis
                  allowDecimals={false}
                  orientation={rtl ? 'right' : 'left'}
                  tickFormatter={(v: number) => fmtNumber(v)}
                  stroke={colors['chart-grid']}
                  tick={{ fill: colors['chart-axis'], fontSize: 12 }}
                  width={44}
                />
                <Tooltip
                  cursor={{ stroke: colors['chart-axis'], strokeWidth: 1 }}
                  content={(props) => (
                    <ChartTooltip
                      active={props.active}
                      title={props.label !== undefined ? fmtDateTime(Number(props.label), { dateStyle: 'medium', timeStyle: 'short' }) : ''}
                      rows={defs.map((d) => ({
                        label: d.label,
                        color: colors[d.color],
                        value: fmtNumber(Number((props.payload?.[0]?.payload as Record<string, number> | undefined)?.[d.key] ?? 0)),
                      }))}
                    />
                  )}
                />
                <Legend
                  verticalAlign="top"
                  align={rtl ? 'right' : 'left'}
                  iconType="plainline"
                  wrapperStyle={{ paddingBottom: 8, color: colors['text'], fontSize: 13 }}
                />
                {defs.map((d) => (
                  <Line
                    key={d.key}
                    type="monotone"
                    dataKey={d.key}
                    name={d.label}
                    stroke={colors[d.color]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 5, strokeWidth: 2, stroke: colors['surface'] }}
                    isAnimationActive={!prefersReducedMotion()}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </Section>
  );
}

function ChartTooltip({ active, title, rows }: { active?: boolean; title: string; rows: { label: string; color: string; value: string }[] }) {
  if (!active) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__title">{title}</p>
      <ul>
        {rows.map((r) => (
          <li key={r.label}>
            <span className="chart-tooltip__key" style={{ backgroundColor: r.color }} aria-hidden="true" />
            <strong>{r.value}</strong>
            <span className="muted">{r.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ByToolCard({ stats }: { stats: StatsOverview }) {
  const { t, fmtNumber } = useI18n();
  const rows = [...(stats.by_tool ?? [])]
    .map((r) => ({ ...r, total: (r.allowed ?? 0) + (r.denied ?? 0) + (r.approval ?? 0) }))
    .sort((a, b) => b.total - a.total);
  const max = Math.max(1, ...rows.map((r) => r.total));
  return (
    <Section id="bytool" title={t('overview.byTool')} subtitle={t('overview.byToolDesc')}>
      {rows.length === 0 ? (
        <EmptyState icon="tool" title={t('overview.noData')} />
      ) : (
        <div className="table-wrap">
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">{t('overview.colTool')}</th>
                <th scope="col" className="num">
                  {t('action.allow')}
                </th>
                <th scope="col" className="num">
                  {t('action.require_approval')}
                </th>
                <th scope="col" className="num">
                  {t('action.deny')}
                </th>
                <th scope="col">{t('overview.colShare')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.tool}>
                  <th scope="row">
                    <code className="code-inline">{r.tool}</code>
                  </th>
                  <td className="num">{fmtNumber(r.allowed)}</td>
                  <td className="num">{fmtNumber(r.approval)}</td>
                  <td className="num">{fmtNumber(r.denied)}</td>
                  <td>
                    <span className="stackbar" style={{ inlineSize: `${Math.max(6, (r.total / max) * 100)}%` }} aria-hidden="true">
                      {r.allowed ? <span className="stackbar__seg stackbar__seg--allow" style={{ flexGrow: r.allowed }} /> : null}
                      {r.approval ? <span className="stackbar__seg stackbar__seg--approval" style={{ flexGrow: r.approval }} /> : null}
                      {r.denied ? <span className="stackbar__seg stackbar__seg--deny" style={{ flexGrow: r.denied }} /> : null}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function ByLayerCard({ stats }: { stats: StatsOverview }) {
  const { t, tx, fmtNumber, dir } = useI18n();
  const colors = useChartColors();
  const [asTable, setAsTable] = useState(false);
  const rtl = dir === 'rtl';
  const rows = [...(stats.by_layer ?? [])]
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count)
    .map((r) => ({ ...r, name: tx(`layer.${r.layer}`, String(r.layer)) }));

  return (
    <Section
      id="bylayer"
      title={t('overview.byLayer')}
      subtitle={t('overview.byLayerDesc')}
      actions={rows.length ? <TableToggle table={asTable} onToggle={() => setAsTable((v) => !v)} controls="bylayer-body" /> : undefined}
    >
      <div id="bylayer-body">
        {rows.length === 0 ? (
          <EmptyState icon="layers" title={t('overview.noObjections')} />
        ) : asTable ? (
          <div className="table-wrap">
            <table className="table table--compact">
              <thead>
                <tr>
                  <th scope="col">{t('overview.colLayer')}</th>
                  <th scope="col" className="num">
                    {t('overview.colCount')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.layer}>
                    <th scope="row">{r.name}</th>
                    <td className="num">{fmtNumber(r.count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="chart" role="img" aria-label={t('overview.byLayerAlt')}>
            <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 44 + 20)}>
              <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 40 }} barCategoryGap={10}>
                <CartesianGrid stroke={colors['chart-grid']} horizontal={false} />
                <XAxis type="number" allowDecimals={false} reversed={rtl} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  orientation={rtl ? 'right' : 'left'}
                  width={96}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: colors['text'], fontSize: 13 }}
                />
                <Tooltip
                  cursor={{ fill: colors['chart-grid'] }}
                  content={(props) => (
                    <ChartTooltip
                      active={props.active}
                      title={String(props.label ?? '')}
                      rows={[{ label: t('overview.colCount'), color: colors['chart-accent'], value: fmtNumber(Number(props.payload?.[0]?.value ?? 0)) }]}
                    />
                  )}
                />
                <Bar
                  dataKey="count"
                  fill={colors['chart-accent']}
                  barSize={20}
                  radius={rtl ? [4, 0, 0, 4] : [0, 4, 4, 0]}
                  isAnimationActive={!prefersReducedMotion()}
                >
                  <LabelList
                    dataKey="count"
                    position={rtl ? 'left' : 'right'}
                    formatter={(v: unknown) => fmtNumber(Number(v))}
                    fill={colors['text']}
                    fontSize={12}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </Section>
  );
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
