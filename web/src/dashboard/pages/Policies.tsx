import { useEffect, useMemo, useRef, useState } from 'react';
import type { PoliciesResponse, PolicyActivation, PolicyDetail, PolicyVersion } from '../../shared/api/types';
import { useApi, useAuth } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { ConfirmDialog, Dialog } from '../../shared/components/Dialog';
import { Icon } from '../../shared/components/Icon';
import { QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { errorLines, shortHash } from '../../shared/lib/format';
import { CodeEditor, type CodeEditorHandle, DiffView } from '../components/CodeEditor';
import { PageHeader, Section } from '../components/PageHeader';

export default function Policies() {
  const api = useApi();
  const { t } = useI18n();
  const query = useQuery((signal) => api.policies(signal), [api]);
  return (
    <div className="stack-lg">
      <PageHeader title={t('policies.title')} subtitle={t('policies.subtitle')} />
      <QueryView {...query}>{(data) => <PolicyWorkspace data={data} reload={query.reload} />}</QueryView>
    </div>
  );
}

type Validation = { valid: boolean; errors: string[] } | null;

function PolicyWorkspace({ data, reload }: { data: PoliciesResponse; reload: () => void }) {
  const api = useApi();
  const toast = useToast();
  const { hasRole } = useAuth();
  const { t, fmtNumber, fmtDateTime } = useI18n();
  const isAdmin = hasRole('admin');
  const activeText = data.active?.yaml_text ?? '';
  const [text, setText] = useState(activeText);
  const [validation, setValidation] = useState<Validation>(null);
  const [validating, setValidating] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [activating, setActivating] = useState(false);
  const [viewing, setViewing] = useState<{ detail: PolicyDetail; mode: 'view' | 'diff' } | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [rollbackTo, setRollbackTo] = useState<PolicyVersion | null>(null);
  const [rollingBack, setRollingBack] = useState(false);
  const editorRef = useRef<CodeEditorHandle>(null);

  // A newly activated version (from here or another admin) resets a clean editor.
  useEffect(() => {
    setText((current) => (current === '' || current === activeText ? activeText : current));
  }, [activeText]);

  const dirty = text !== activeText;
  const lines = useMemo(() => errorLines(validation?.errors ?? []), [validation]);
  const monitorMode = /^mode\s*:\s*monitor\b/m.test(text);

  async function validate(): Promise<boolean> {
    setValidating(true);
    try {
      const result = await api.validatePolicy(text);
      setValidation(result);
      return result.valid;
    } catch (err) {
      toast.error(err);
      return false;
    } finally {
      setValidating(false);
    }
  }

  function announceActivation(res: PolicyActivation) {
    toast.success(t('policies.activated', { version: shortHash(res?.version ?? '', 12) }));
    if (res?.mode === 'monitor') toast.show('warning', t('policies.activatedMonitor'));
  }

  async function rollback() {
    if (!rollbackTo) return;
    setRollingBack(true);
    try {
      const res = await api.rollbackPolicy(rollbackTo.version);
      announceActivation(res);
      setRollbackTo(null);
      setViewing(null);
      setValidation(null);
      reload();
    } catch (err) {
      toast.error(err);
    } finally {
      setRollingBack(false);
    }
  }

  async function activate() {
    setActivating(true);
    try {
      const res = await api.activatePolicy(text, comment.trim() || undefined);
      announceActivation(res);
      setConfirmOpen(false);
      setComment('');
      setValidation(null);
      reload();
    } catch (err) {
      toast.error(err);
    } finally {
      setActivating(false);
    }
  }

  async function open(version: PolicyVersion, mode: 'view' | 'diff') {
    try {
      const detail = await api.policy(version.version);
      setViewing({ detail, mode });
    } catch (err) {
      toast.error(err);
    }
  }

  return (
    <>
      <Section
        id="editor"
        title={
          <>
            <Icon name="file-text" size={18} />
            {t('policies.editor')}
            {dirty ? <span className="badge badge--warn">{t('policies.unsaved')}</span> : null}
            {monitorMode ? (
              <span className="badge badge--info" title={t('policies.monitorModeHint')}>
                <Icon name="eye" size={14} />
                {t('policies.monitorMode')}
              </span>
            ) : null}
          </>
        }
        subtitle={
          data.active
            ? t('policies.activeInfo', {
                version: shortHash(data.active.version, 12),
                by: data.active.created_by ?? '–',
                when: fmtDateTime(data.active.created_at, { dateStyle: 'medium', timeStyle: 'short' }),
              })
            : t('policies.noActive')
        }
        actions={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setShowDiff((v) => !v)} aria-pressed={showDiff} disabled={!dirty}>
              <Icon name="diff" size={16} />
              {t('policies.compareActive')}
            </button>
            {isAdmin ? (
              <>
                <button type="button" className="btn btn--ghost btn--sm" onClick={() => setText(activeText)} disabled={!dirty}>
                  {t('policies.revert')}
                </button>
                <button type="button" className="btn btn--ghost btn--sm" onClick={validate} disabled={validating} aria-busy={validating}>
                  <Icon name="check-circle" size={16} />
                  {t('policies.validate')}
                </button>
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={!dirty || activating}
                  onClick={async () => {
                    if (await validate()) setConfirmOpen(true);
                  }}
                >
                  <Icon name="zap" size={16} />
                  {t('policies.activate')}
                </button>
              </>
            ) : null}
          </>
        }
      >
        {!isAdmin ? (
          <p className="banner banner--info small">
            <Icon name="lock" size={16} />
            {t('policies.readOnly')}
          </p>
        ) : (
          <p className="muted small" id="editor-hint">
            {t('policies.editorHint')}
          </p>
        )}

        <div aria-live="polite">
          {validation ? (
            validation.valid ? (
              <p className="banner banner--allow">
                <Icon name="check-circle" />
                {t('policies.valid')}
              </p>
            ) : (
              <div className="banner banner--deny" role="alert">
                <Icon name="alert" />
                <div className="banner__body">
                  <strong>{t('policies.invalid', { count: fmtNumber(validation.errors.length) })}</strong>
                  <ul className="error-list">
                    {validation.errors.map((err, i) => {
                      const line = /\bline\s+(\d+)/i.exec(err)?.[1];
                      return (
                        <li key={i}>
                          <span className="mono small">{err}</span>{' '}
                          {line ? (
                            <button type="button" className="btn btn--link btn--sm" onClick={() => editorRef.current?.goToLine(Number(line))}>
                              {t('policies.jumpToLine', { line })}
                            </button>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
            )
          ) : null}
        </div>

        <CodeEditor
          ref={editorRef}
          id="policy-editor"
          label={t('policies.editor')}
          describedBy="editor-hint"
          value={text}
          onChange={(v) => {
            setText(v);
            setValidation(null);
          }}
          readOnly={!isAdmin}
          errorLines={lines}
        />
        <p className="muted small editor-stats">{t('policies.lineCount', { count: fmtNumber(text.split('\n').length) })}</p>

        {showDiff && dirty ? (
          <div className="stack-sm">
            <h3>{t('policies.diffTitle', { from: shortHash(data.active?.version, 10) })}</h3>
            <DiffView oldText={activeText} newText={text} />
          </div>
        ) : null}
      </Section>

      <Section
        id="versions"
        title={
          <>
            <Icon name="layers" size={18} />
            {t('policies.versions')}
          </>
        }
      >
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('policies.colVersion')}</th>
                <th scope="col">{t('policies.colCreated')}</th>
                <th scope="col">{t('policies.colBy')}</th>
                <th scope="col">{t('policies.colComment')}</th>
                <th scope="col">{t('app.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {data.versions.map((v) => (
                <tr key={v.version}>
                  <td>
                    <code className="code-inline" title={v.version}>
                      {shortHash(v.version, 12)}
                    </code>{' '}
                    {v.active || v.version === data.active?.version ? (
                      <span className="badge badge--allow">
                        <Icon name="check" size={12} />
                        {t('policies.active')}
                      </span>
                    ) : null}
                  </td>
                  <td>{fmtDateTime(v.created_at, { dateStyle: 'medium', timeStyle: 'short' })}</td>
                  <td>{v.created_by ?? '–'}</td>
                  <td dir="auto">{v.comment ?? ''}</td>
                  <td>
                    <div className="row">
                      <button type="button" className="btn btn--ghost btn--sm" onClick={() => open(v, 'view')}>
                        <Icon name="eye" size={14} />
                        {t('app.view')}
                      </button>
                      <button type="button" className="btn btn--ghost btn--sm" onClick={() => open(v, 'diff')}>
                        <Icon name="diff" size={14} />
                        {t('policies.diff')}
                      </button>
                      {isAdmin && !(v.active || v.version === data.active?.version) ? (
                        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setRollbackTo(v)}>
                          <Icon name="refresh" size={14} />
                          {t('policies.rollback')}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <ConfirmDialog
        open={rollbackTo !== null}
        title={t('policies.rollbackTitle')}
        body={
          <p>
            {t('policies.rollbackBody', {
              version: shortHash(rollbackTo?.version, 12),
              when: rollbackTo ? fmtDateTime(rollbackTo.created_at, { dateStyle: 'medium', timeStyle: 'short' }) : '–',
            })}
          </p>
        }
        confirmLabel={t('policies.rollback')}
        pending={rollingBack}
        onConfirm={rollback}
        onClose={() => setRollbackTo(null)}
      />

      <ConfirmDialog
        open={confirmOpen}
        title={t('policies.activateTitle')}
        body={<p>{t('policies.activateBody')}</p>}
        confirmLabel={t('policies.activate')}
        pending={activating}
        onConfirm={activate}
        onClose={() => setConfirmOpen(false)}
      >
        <div className="field">
          <label className="field__label" htmlFor="policy-comment">
            {t('policies.comment')}
          </label>
          <input id="policy-comment" className="input" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} dir="auto" />
        </div>
        {dirty ? (
          <details className="stack-sm">
            <summary>{t('policies.reviewChanges')}</summary>
            <DiffView oldText={activeText} newText={text} />
          </details>
        ) : null}
      </ConfirmDialog>

      {viewing ? (
        <Dialog
          open
          onClose={() => setViewing(null)}
          size="lg"
          title={
            viewing.mode === 'view'
              ? t('policies.viewing', { version: shortHash(viewing.detail.version, 12) })
              : t('policies.diffVersionTitle', { version: shortHash(viewing.detail.version, 12) })
          }
          footer={
            isAdmin ? (
              <>
                {viewing.detail.version !== data.active?.version ? (
                  <button type="button" className="btn btn--ghost" onClick={() => setRollbackTo(viewing.detail)}>
                    <Icon name="refresh" size={16} />
                    {t('policies.rollback')}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => {
                    setText(viewing.detail.yaml_text);
                    setValidation(null);
                    setViewing(null);
                  }}
                >
                  <Icon name="file-text" size={16} />
                  {t('policies.load')}
                </button>
              </>
            ) : undefined
          }
        >
          {viewing.mode === 'view' ? (
            <CodeEditor value={viewing.detail.yaml_text} readOnly label={t('policies.viewing', { version: shortHash(viewing.detail.version, 12) })} rows={22} />
          ) : (
            <DiffView oldText={viewing.detail.yaml_text} newText={text} />
          )}
        </Dialog>
      ) : null}
    </>
  );
}
