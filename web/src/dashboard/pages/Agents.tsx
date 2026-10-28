import { type FormEvent, useState } from 'react';
import type { Agent, AgentWithKey } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { CopyButton } from '../../shared/components/CopyButton';
import { ConfirmDialog, Dialog } from '../../shared/components/Dialog';
import { Icon } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { policyAgentIds } from '../../shared/lib/format';
import { PageHeader, Section } from '../components/PageHeader';

/** Same pattern as the server (SLUG_PATTERN in api/schemas.py). */
export const SLUG_RE = /^[a-z0-9][a-z0-9_-]{1,63}$/;

export default function Agents() {
  const api = useApi();
  const toast = useToast();
  const { t, fmtDateTime, fmtRelative } = useI18n();
  const query = useQuery((signal) => api.agents(signal), [api]);
  const policyIds = useQuery((signal) => api.policies(signal).then((p) => policyAgentIds(p.active?.yaml_text ?? '')).catch(() => [] as string[]), [api]);
  const [creating, setCreating] = useState(false);
  const [revealed, setRevealed] = useState<AgentWithKey | null>(null);
  const [confirm, setConfirm] = useState<{ kind: 'rotate' | 'delete'; agent: Agent } | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggle(agent: Agent) {
    try {
      await api.updateAgent(agent.id, { disabled: !agent.disabled });
      toast.success(t(agent.disabled ? 'agents.enabledMsg' : 'agents.disabledMsg', { name: agent.name }));
      query.reload();
    } catch (err) {
      toast.error(err);
    }
  }

  async function runConfirm() {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.kind === 'rotate') {
        setRevealed(await api.rotateAgentKey(confirm.agent.id));
      } else {
        await api.deleteAgent(confirm.agent.id);
        toast.success(t('agents.deleted', { name: confirm.agent.name }));
      }
      setConfirm(null);
      query.reload();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader
        title={t('agents.title')}
        subtitle={t('agents.subtitle')}
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            <Icon name="plus" size={18} />
            {t('agents.create')}
          </button>
        }
      />
      <p className="banner banner--info small">
        <Icon name="key" size={16} />
        <span>
          {t('agents.usage')} <code className="code-inline">Authorization: Bearer mk_…</code> · <code className="code-inline">X-Mirsad-Key</code>
        </span>
      </p>
      <Section id="agents" title={t('agents.title')}>
        <QueryView {...query}>
          {(agents) =>
            agents.length === 0 ? (
              <EmptyState icon="key" title={t('agents.empty')} />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t('agents.name')}</th>
                      <th scope="col">{t('agents.policyAgent')}</th>
                      <th scope="col">{t('agents.colKey')}</th>
                      <th scope="col">{t('agents.colLastSeen')}</th>
                      <th scope="col">{t('app.status')}</th>
                      <th scope="col">{t('app.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((agent) => (
                      <tr key={agent.id}>
                        <td>
                          <strong>{agent.name}</strong>
                          <div className="mono small muted">{agent.id}</div>
                          {agent.description ? <div className="small muted">{agent.description}</div> : null}
                        </td>
                        <td className="mono small">{agent.policy_agent_id}</td>
                        <td className="mono small">{agent.key_prefix ? `mk_${agent.key_prefix}_…` : '–'}</td>
                        <td title={agent.last_seen_at ? fmtDateTime(agent.last_seen_at) : undefined}>
                          {agent.last_seen_at ? fmtRelative(agent.last_seen_at) : t('agents.never')}
                        </td>
                        <td>
                          {agent.disabled ? (
                            <span className="badge badge--neutral">
                              <Icon name="pause" size={12} />
                              {t('app.disabled')}
                            </span>
                          ) : (
                            <span className="badge badge--allow">
                              <Icon name="check" size={12} />
                              {t('app.enabled')}
                            </span>
                          )}
                        </td>
                        <td>
                          <div className="row">
                            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setConfirm({ kind: 'rotate', agent })}>
                              <Icon name="refresh" size={14} />
                              {t('agents.rotate')}
                            </button>
                            <button type="button" className="btn btn--ghost btn--sm" onClick={() => toggle(agent)}>
                              {agent.disabled ? t('agents.enable') : t('agents.disable')}
                            </button>
                            <button
                              type="button"
                              className="icon-btn icon-btn--sm"
                              onClick={() => setConfirm({ kind: 'delete', agent })}
                              aria-label={t('agents.deleteLabel', { name: agent.name })}
                              title={t('app.delete')}
                            >
                              <Icon name="trash" size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryView>
      </Section>

      {creating ? (
        <CreateAgentDialog
          suggestions={policyIds.data ?? []}
          onClose={() => setCreating(false)}
          onCreated={(res) => {
            setCreating(false);
            setRevealed(res);
            query.reload();
          }}
        />
      ) : null}

      {revealed ? <KeyReveal result={revealed} onClose={() => setRevealed(null)} /> : null}

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.kind === 'rotate' ? t('agents.rotate') : t('app.delete')}
        body={
          <p>
            {confirm?.kind === 'rotate'
              ? t('agents.rotateConfirm', { name: confirm?.agent.name ?? '' })
              : t('agents.deleteConfirm', { name: confirm?.agent.name ?? '' })}
          </p>
        }
        confirmLabel={confirm?.kind === 'rotate' ? t('agents.rotate') : t('app.delete')}
        tone="danger"
        pending={busy}
        onConfirm={runConfirm}
        onClose={() => setConfirm(null)}
      />
    </div>
  );
}

function CreateAgentDialog({ suggestions, onClose, onCreated }: { suggestions: string[]; onClose: () => void; onCreated: (r: AgentWithKey) => void }) {
  const api = useApi();
  const toast = useToast();
  const { t } = useI18n();
  const [form, setForm] = useState({ id: '', name: '', policy_agent_id: suggestions[0] ?? '', description: '' });
  const [pending, setPending] = useState(false);
  const idValid = SLUG_RE.test(form.id);
  const valid = idValid && form.name.trim() !== '' && form.policy_agent_id.trim() !== '';

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setPending(true);
    try {
      const res = await api.createAgent({
        id: form.id,
        name: form.name.trim(),
        policy_agent_id: form.policy_agent_id.trim(),
        description: form.description.trim() || undefined,
      });
      toast.success(t('agents.created', { name: res.agent?.name ?? form.name }));
      onCreated(res);
    } catch (err) {
      toast.error(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={t('agents.create')}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            {t('app.cancel')}
          </button>
          <button type="submit" form="agent-form" className="btn btn--primary" disabled={!valid || pending} aria-busy={pending}>
            {t('app.create')}
          </button>
        </>
      }
    >
      <form id="agent-form" className="stack" onSubmit={submit}>
        <div className="field">
          <label className="field__label" htmlFor="agent-name">
            {t('agents.name')}
          </label>
          <input
            id="agent-name"
            className="input"
            maxLength={128}
            value={form.name}
            onChange={(e) => {
              const name = e.target.value;
              setForm((f) => ({
                ...f,
                name,
                // Suggest a slug from the name until the user edits the id themselves.
                id: f.id === slugify(f.name) ? slugify(name) : f.id,
              }));
            }}
            required
            dir="auto"
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="agent-id">
            {t('agents.id')}
          </label>
          <input
            id="agent-id"
            className="input mono"
            maxLength={64}
            value={form.id}
            onChange={(e) => setForm((f) => ({ ...f, id: e.target.value.toLowerCase() }))}
            aria-invalid={form.id !== '' && !idValid ? true : undefined}
            aria-describedby="agent-id-hint"
            required
            dir="ltr"
          />
          <span className="field__hint" id="agent-id-hint">
            {t('agents.idHint')}
          </span>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="agent-policy">
            {t('agents.policyAgent')}
          </label>
          <input
            id="agent-policy"
            className="input mono"
            list="policy-agent-ids"
            value={form.policy_agent_id}
            onChange={(e) => setForm((f) => ({ ...f, policy_agent_id: e.target.value }))}
            aria-describedby="agent-policy-hint"
            required
            dir="ltr"
          />
          <datalist id="policy-agent-ids">
            {suggestions.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
          <span className="field__hint" id="agent-policy-hint">
            {t('agents.policyAgentHint')}
          </span>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="agent-desc">
            {t('agents.description')} <span className="muted">({t('app.optional')})</span>
          </label>
          <textarea
            id="agent-desc"
            className="textarea"
            rows={2}
            maxLength={1000}
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            dir="auto"
          />
        </div>
      </form>
    </Dialog>
  );
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
}

/** The full key is shown exactly once; closing requires acknowledging it was stored. */
function KeyReveal({ result, onClose }: { result: AgentWithKey; onClose: () => void }) {
  const { t } = useI18n();
  const [stored, setStored] = useState(false);
  return (
    <Dialog
      open
      onClose={() => {
        if (stored) onClose();
      }}
      title={
        <>
          <Icon name="key" />
          {t('agents.keyTitle', { name: result.agent?.name ?? result.agent?.id ?? '' })}
        </>
      }
      footer={
        <button type="button" className="btn btn--primary" onClick={onClose} disabled={!stored}>
          {t('app.done')}
        </button>
      }
    >
      <div className="stack">
        <p className="banner banner--warn" role="alert">
          <Icon name="alert" />
          <span>{t('agents.keyWarning')}</span>
        </p>
        {result.warnings?.length ? (
          <div className="banner banner--deny">
            <Icon name="info" />
            <div className="banner__body">
              <strong>{t('agents.serverWarnings')}</strong>
              <ul className="error-list">
                {result.warnings.map((w) => (
                  <li key={w} className="small">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
        <div className="field">
          <span className="field__label" id="key-label">
            {t('agents.keyLabel')}
          </span>
          <div className="key-box" dir="ltr">
            <code aria-labelledby="key-label" className="key-box__value">
              {result.api_key}
            </code>
            <CopyButton text={result.api_key} variant="primary" />
          </div>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={stored} onChange={(e) => setStored(e.target.checked)} />
          <span>{t('agents.keyStored')}</span>
        </label>
      </div>
    </Dialog>
  );
}
