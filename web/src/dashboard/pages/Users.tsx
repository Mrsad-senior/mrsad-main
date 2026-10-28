import { type FormEvent, useState } from 'react';
import { type Lang, ROLES, type Role, type User, type UserCreated } from '../../shared/api/types';
import { useApi, useAuth } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { CopyButton } from '../../shared/components/CopyButton';
import { ConfirmDialog, Dialog } from '../../shared/components/Dialog';
import { Icon } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { PageHeader, Section } from '../components/PageHeader';

/** Same rules as the server (api/routers/users.py, api/schemas.py). */
export const MIN_PASSWORD = 10;
export const USERNAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}$/;

export default function Users() {
  const api = useApi();
  const toast = useToast();
  const { user: me } = useAuth();
  const { t, fmtDateTime } = useI18n();
  const query = useQuery((signal) => api.users(signal), [api]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [created, setCreated] = useState<UserCreated | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);

  async function patch(user: User, change: Partial<User>) {
    try {
      await api.updateUser(user.username, change);
      toast.success(t('users.updated', { name: user.username }));
      query.reload();
    } catch (err) {
      toast.error(err);
    }
  }

  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api.deleteUser(deleting.username);
      toast.success(t('users.deleted', { name: deleting.username }));
      setDeleting(null);
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
        title={t('users.title')}
        subtitle={t('users.subtitle')}
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            <Icon name="plus" size={18} />
            {t('users.create')}
          </button>
        }
      />
      <Section id="roles" title={t('users.rolesTitle')}>
        <dl className="role-help">
          {ROLES.map((role) => (
            <div key={role}>
              <dt>{t(`roles.${role}`)}</dt>
              <dd className="muted">{t(`users.roleHelp.${role}`)}</dd>
            </div>
          ))}
        </dl>
      </Section>
      <Section id="users" title={t('users.title')}>
        <QueryView {...query}>
          {(users) =>
            users.length === 0 ? (
              <EmptyState icon="users" title={t('users.empty')} />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t('users.username')}</th>
                      <th scope="col">{t('users.role')}</th>
                      <th scope="col">{t('users.lang')}</th>
                      <th scope="col">{t('users.colCreated')}</th>
                      <th scope="col">{t('app.status')}</th>
                      <th scope="col">{t('app.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => {
                      const self = u.username === me?.username;
                      return (
                        <tr key={u.username}>
                          <td>
                            <strong>{u.display_name || u.username}</strong> {self ? <span className="muted small">{t('users.you')}</span> : null}
                            <div className="mono small muted">{u.username}</div>
                          </td>
                          <td>
                            <label className="visually-hidden" htmlFor={`role-${u.username}`}>
                              {t('users.roleFor', { name: u.username })}
                            </label>
                            <select
                              id={`role-${u.username}`}
                              className="select select--sm"
                              value={u.role}
                              disabled={self}
                              onChange={(e) => patch(u, { role: e.target.value as Role })}
                            >
                              {ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {t(`roles.${r}`)}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>{u.lang === 'ar' ? 'العربية' : 'English'}</td>
                          <td>{u.created_at ? fmtDateTime(u.created_at, { dateStyle: 'medium' }) : '–'}</td>
                          <td>
                            {u.disabled ? (
                              <span className="badge badge--neutral">{t('app.disabled')}</span>
                            ) : (
                              <span className="badge badge--allow">{t('app.enabled')}</span>
                            )}
                          </td>
                          <td>
                            <div className="row">
                              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(u)}>
                                {t('users.edit')}
                              </button>
                              <button type="button" className="btn btn--ghost btn--sm" disabled={self} onClick={() => patch(u, { disabled: !u.disabled })}>
                                {u.disabled ? t('agents.enable') : t('agents.disable')}
                              </button>
                              <button
                                type="button"
                                className="icon-btn icon-btn--sm"
                                disabled={self}
                                onClick={() => setDeleting(u)}
                                aria-label={t('users.deleteLabel', { name: u.username })}
                                title={t('app.delete')}
                              >
                                <Icon name="trash" size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryView>
      </Section>

      {creating ? (
        <CreateUserDialog
          onClose={() => setCreating(false)}
          onCreated={(res) => {
            setCreating(false);
            if (res.generated_password) setCreated(res);
            query.reload();
          }}
        />
      ) : null}

      {editing ? (
        <EditUserDialog
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            query.reload();
          }}
        />
      ) : null}

      {created?.generated_password ? (
        <PasswordReveal username={created.user.username} password={created.generated_password} onClose={() => setCreated(null)} />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title={t('app.delete')}
        body={<p>{t('users.deleteConfirm', { name: deleting?.username ?? '' })}</p>}
        confirmLabel={t('app.delete')}
        tone="danger"
        pending={busy}
        onConfirm={remove}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}

function CreateUserDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (res: UserCreated) => void }) {
  const api = useApi();
  const toast = useToast();
  const { t } = useI18n();
  const [form, setForm] = useState({ username: '', display_name: '', role: 'approver' as Role, lang: 'en' as Lang, password: '' });
  const [generate, setGenerate] = useState(true);
  const [pending, setPending] = useState(false);
  const usernameOk = USERNAME_RE.test(form.username);
  const passwordOk = generate || form.password.length >= MIN_PASSWORD;
  const valid = usernameOk && passwordOk;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setPending(true);
    try {
      const res = await api.createUser({
        username: form.username,
        role: form.role,
        lang: form.lang,
        display_name: form.display_name.trim() || undefined,
        password: generate ? undefined : form.password,
      });
      toast.success(t('users.created', { name: form.username }));
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
      title={t('users.create')}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            {t('app.cancel')}
          </button>
          <button type="submit" form="user-form" className="btn btn--primary" disabled={!valid || pending} aria-busy={pending}>
            {t('app.create')}
          </button>
        </>
      }
    >
      <form id="user-form" className="stack" onSubmit={submit} autoComplete="off">
        <div className="field">
          <label className="field__label" htmlFor="user-name">
            {t('users.username')}
          </label>
          <input
            id="user-name"
            className="input"
            value={form.username}
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value.trim() }))}
            autoCapitalize="none"
            aria-invalid={form.username !== '' && !usernameOk ? true : undefined}
            aria-describedby="user-name-hint"
            required
            dir="ltr"
          />
          <span className="field__hint" id="user-name-hint">
            {t('users.usernameHint')}
          </span>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="user-display">
            {t('users.displayName')} <span className="muted">({t('app.optional')})</span>
          </label>
          <input
            id="user-display"
            className="input"
            value={form.display_name}
            maxLength={128}
            onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
            dir="auto"
          />
        </div>
        <div className="form-grid">
          <div className="field">
            <label className="field__label" htmlFor="user-role">
              {t('users.role')}
            </label>
            <select id="user-role" className="select" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as Role }))}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="user-lang">
              {t('users.lang')}
            </label>
            <select id="user-lang" className="select" value={form.lang} onChange={(e) => setForm((f) => ({ ...f, lang: e.target.value as Lang }))}>
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
          </div>
        </div>
        <p className="field__hint">{t(`users.roleHelp.${form.role}`)}</p>
        <label className="checkbox">
          <input type="checkbox" checked={generate} onChange={(e) => setGenerate(e.target.checked)} />
          <span>{t('users.generatePassword')}</span>
        </label>
        {!generate ? (
          <div className="field">
            <label className="field__label" htmlFor="user-password">
              {t('users.password')}
            </label>
            <input
              id="user-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={form.password}
              maxLength={1024}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              aria-invalid={form.password !== '' && !passwordOk ? true : undefined}
              aria-describedby="user-password-hint"
              required
              dir="ltr"
            />
            <span className="field__hint" id="user-password-hint">
              {t('users.passwordHint', { min: MIN_PASSWORD })}
            </span>
          </div>
        ) : null}
      </form>
    </Dialog>
  );
}

/** Display name, language and an optional password reset (role and status are edited inline). */
function EditUserDialog({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: () => void }) {
  const api = useApi();
  const toast = useToast();
  const { t } = useI18n();
  const [displayName, setDisplayName] = useState(user.display_name ?? '');
  const [lang, setLang] = useState<Lang>(user.lang === 'ar' ? 'ar' : 'en');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const passwordOk = password === '' || password.length >= MIN_PASSWORD;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!passwordOk) return;
    setPending(true);
    try {
      const patch: Parameters<typeof api.updateUser>[1] = { display_name: displayName.trim(), lang };
      if (password) patch.password = password;
      await api.updateUser(user.username, patch);
      toast.success(t('users.updated', { name: user.username }));
      onSaved();
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
      title={t('users.editTitle', { name: user.username })}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            {t('app.cancel')}
          </button>
          <button type="submit" form="user-edit-form" className="btn btn--primary" disabled={!passwordOk || pending} aria-busy={pending}>
            {t('app.save')}
          </button>
        </>
      }
    >
      <form id="user-edit-form" className="stack" onSubmit={submit} autoComplete="off">
        <div className="field">
          <label className="field__label" htmlFor="edit-display">
            {t('users.displayName')}
          </label>
          <input id="edit-display" className="input" value={displayName} maxLength={128} onChange={(e) => setDisplayName(e.target.value)} dir="auto" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="edit-lang">
            {t('users.lang')}
          </label>
          <select id="edit-lang" className="select" value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="en">English</option>
            <option value="ar">العربية</option>
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="edit-password">
            {t('users.newPassword')} <span className="muted">({t('app.optional')})</span>
          </label>
          <input
            id="edit-password"
            className="input"
            type="password"
            autoComplete="new-password"
            value={password}
            maxLength={1024}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!passwordOk ? true : undefined}
            aria-describedby="edit-password-hint"
            dir="ltr"
          />
          <span className="field__hint" id="edit-password-hint">
            {t('users.newPasswordHint', { min: MIN_PASSWORD })}
          </span>
        </div>
      </form>
    </Dialog>
  );
}

/** A server-generated password is shown exactly once; closing requires acknowledging it. */
function PasswordReveal({ username, password, onClose }: { username: string; password: string; onClose: () => void }) {
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
          {t('users.passwordTitle', { name: username })}
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
          <span>{t('users.passwordOnce')}</span>
        </p>
        <div className="key-box" dir="ltr">
          <code className="key-box__value" aria-label={t('users.password')}>
            {password}
          </code>
          <CopyButton text={password} variant="primary" />
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={stored} onChange={(e) => setStored(e.target.checked)} />
          <span>{t('users.passwordStored')}</span>
        </label>
      </div>
    </Dialog>
  );
}
