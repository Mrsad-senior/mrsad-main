import { useMemo, useState } from 'react';
import type { DiscoveredTool, ToolProfile } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { RiskBadge } from '../../shared/components/Badges';
import { Icon } from '../../shared/components/Icon';
import { JsonView } from '../../shared/components/JsonView';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { PageHeader, Section } from '../components/PageHeader';

export default function Tools() {
  const api = useApi();
  const { t } = useI18n();
  const query = useQuery((signal) => api.tools(signal), [api]);
  return (
    <div className="stack-lg">
      <PageHeader title={t('tools.title')} subtitle={t('tools.subtitle')} />
      <QueryView {...query}>{(tools) => <ToolsBody tools={tools} />}</QueryView>
    </div>
  );
}

function ToolsBody({ tools }: { tools: DiscoveredTool[] }) {
  const { t } = useI18n();
  const agents = useMemo(() => [...new Set(tools.flatMap((tool) => Object.keys(tool.profiles)))].sort(), [tools]);
  const [agent, setAgent] = useState(agents[0] ?? '');
  const [filter, setFilter] = useState('');
  const visible = tools.filter((tool) => tool.name.toLowerCase().includes(filter.trim().toLowerCase()));

  if (tools.length === 0) return <EmptyState icon="tool" title={t('tools.empty')} />;

  return (
    <Section
      id="tools"
      title={t('tools.title')}
      actions={
        <>
          <label className="row small">
            <span>{t('tools.agent')}</span>
            <select className="select select--sm" value={agent} onChange={(e) => setAgent(e.target.value)} disabled={agents.length === 0}>
              {agents.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="row small">
            <Icon name="search" size={16} />
            <span className="visually-hidden">{t('tools.filter')}</span>
            <input className="input input--sm" type="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t('tools.filter')} dir="ltr" />
          </label>
        </>
      }
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t('tools.colName')}</th>
              <th scope="col">{t('tools.colAllowed')}</th>
              <th scope="col">{t('tools.colTrust')}</th>
              <th scope="col">{t('tools.colSensitivity')}</th>
              <th scope="col">{t('tools.colSink')}</th>
              <th scope="col">{t('tools.colRisk')}</th>
              <th scope="col">{t('tools.colApproval')}</th>
              <th scope="col">{t('tools.colScan')}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((tool) => (
              <ToolRow key={`${tool.upstream ?? ''}:${tool.name}`} tool={tool} profile={tool.profiles[agent] ?? tool.profiles['*']} />
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function ToolRow({ tool, profile }: { tool: DiscoveredTool; profile: ToolProfile | undefined }) {
  const { t } = useI18n();
  const yes = (v: boolean) =>
    v ? (
      <span className="badge badge--allow">
        <Icon name="check" size={12} />
        {t('app.yes')}
      </span>
    ) : (
      <span className="badge badge--neutral">
        <Icon name="x" size={12} />
        {t('app.no')}
      </span>
    );
  return (
    <tr>
      <th scope="row">
        <code className="code-inline">{tool.name}</code>
        {tool.upstream ? <span className="tag">{tool.upstream}</span> : null}
        {tool.description ? <div className="small muted tool-desc">{tool.description}</div> : null}
        {tool.input_schema ? (
          <details className="evidence">
            <summary>{t('tools.schema')}</summary>
            <JsonView value={tool.input_schema} openDepth={2} />
          </details>
        ) : null}
      </th>
      {profile ? (
        <>
          <td>{yes(profile.allowed)}</td>
          <td>
            <span className={`tag tag--${profile.trust}`}>{t(`trust.${profile.trust}`)}</span>
          </td>
          <td>{t(`sensitivity.${profile.sensitivity}`)}</td>
          <td>
            {t(`sink.${profile.sink}`)}
            {profile.sink_params?.length ? <div className="mono small muted">{profile.sink_params.join(', ')}</div> : null}
          </td>
          <td>
            <RiskBadge risk={profile.risk} />
          </td>
          <td>{t(`approvalMode.${profile.approval}`)}</td>
          <td>{yes(profile.scan)}</td>
        </>
      ) : (
        <td colSpan={7} className="muted">
          {t('tools.noProfile')}
        </td>
      )}
    </tr>
  );
}
