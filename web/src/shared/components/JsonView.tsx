import { useI18n } from '../i18n';
import { safeJson } from '../lib/format';
import { CopyButton } from './CopyButton';

/** Collapsible JSON tree built from <details>, so it is keyboard- and screen-reader-friendly. */
export function JsonView({ value, label, openDepth = 1 }: { value: unknown; label?: string; openDepth?: number }) {
  const { t } = useI18n();
  return (
    <div className="json-view" dir="ltr">
      <div className="json-view__toolbar">
        {label ? <span className="json-view__label">{label}</span> : <span />}
        <CopyButton text={safeJson(value)} label={t('app.copyJson')} />
      </div>
      <div className="json-view__tree">
        <JsonNode value={value} depth={0} openDepth={openDepth} />
      </div>
    </div>
  );
}

function JsonNode({ value, depth, openDepth, name }: { value: unknown; depth: number; openDepth: number; name?: string }) {
  const { t, fmtNumber } = useI18n();
  const keyLabel = name !== undefined ? <span className="json-key">{JSON.stringify(name)}: </span> : null;

  if (value === null || typeof value !== 'object') {
    return (
      <div className="json-row">
        {keyLabel}
        <JsonScalar value={value} />
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const entries: [string, unknown][] = isArray ? value.map((v, i) => [String(i), v]) : Object.entries(value as Record<string, unknown>);
  const [open, close] = isArray ? ['[', ']'] : ['{', '}'];

  if (entries.length === 0) {
    return (
      <div className="json-row">
        {keyLabel}
        <span className="json-punct">{`${open}${close}`}</span>
      </div>
    );
  }

  return (
    <details className="json-node" open={depth < openDepth}>
      <summary>
        {keyLabel}
        <span className="json-punct">{open}</span>
        <span className="json-count">
          {' '}
          {t(isArray ? 'json.items' : 'json.keys', { count: fmtNumber(entries.length) })}{' '}
        </span>
        <span className="json-punct json-close-collapsed">{close}</span>
      </summary>
      <div className="json-children">
        {entries.map(([key, child]) => (
          <JsonNode key={key} name={isArray ? undefined : key} value={child} depth={depth + 1} openDepth={openDepth} />
        ))}
      </div>
      <span className="json-punct">{close}</span>
    </details>
  );
}

function JsonScalar({ value }: { value: unknown }) {
  if (value === null) return <span className="json-null">null</span>;
  switch (typeof value) {
    case 'string':
      return (
        <span className="json-string" dir="auto">
          {JSON.stringify(value)}
        </span>
      );
    case 'number':
      return <span className="json-number">{String(value)}</span>;
    case 'boolean':
      return <span className="json-bool">{String(value)}</span>;
    default:
      return <span className="json-null">{String(value)}</span>;
  }
}
