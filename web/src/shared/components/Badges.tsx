/**
 * Status badges. Every badge pairs colour with an icon and a text label, so meaning
 * never depends on colour alone (WCAG 1.4.1).
 */
import type { Action, ApprovalStatus, DetectionLabel, InspectionAction, Layer, Risk } from '../api/types';
import { useI18n } from '../i18n';
import { Icon, type IconName } from './Icon';

type Tone = 'allow' | 'deny' | 'warn' | 'info' | 'neutral' | 'serious' | 'critical';

function Badge({ tone, icon, children, title, size }: { tone: Tone; icon?: IconName; children: string; title?: string; size?: 'sm' | 'lg' }) {
  return (
    <span className={`badge badge--${tone}${size ? ` badge--${size}` : ''}`} title={title}>
      {icon ? <Icon name={icon} size={size === 'lg' ? 18 : 14} strokeWidth={2.2} /> : null}
      <span>{children}</span>
    </span>
  );
}

const ACTION_STYLE: Record<Action, [Tone, IconName]> = {
  allow: ['allow', 'check-circle'],
  require_approval: ['warn', 'pause'],
  deny: ['deny', 'x-octagon'],
};

export function DecisionBadge({ action, size }: { action: Action | string | null | undefined; size?: 'sm' | 'lg' }) {
  const { t, tx } = useI18n();
  if (!action) return <Badge tone="neutral">{t('app.none')}</Badge>;
  const [tone, icon] = ACTION_STYLE[action as Action] ?? ['neutral', 'info'];
  return (
    <Badge tone={tone} icon={icon} size={size}>
      {tx(`action.${action}`, action)}
    </Badge>
  );
}

const INSPECTION_STYLE: Record<InspectionAction, [Tone, IconName]> = {
  pass: ['allow', 'check'],
  flag: ['info', 'eye'],
  sanitize: ['warn', 'shield-alert'],
  block: ['deny', 'x-octagon'],
};

export function InspectionBadge({ action }: { action: InspectionAction | string | null | undefined }) {
  const { t, tx } = useI18n();
  if (!action) return <Badge tone="neutral">{t('app.none')}</Badge>;
  const [tone, icon] = INSPECTION_STYLE[action as InspectionAction] ?? ['neutral', 'info'];
  return (
    <Badge tone={tone} icon={icon}>
      {tx(`inspection.${action}`, action)}
    </Badge>
  );
}

const RISK_STYLE: Record<Risk, [Tone, IconName]> = {
  low: ['allow', 'shield-check'],
  medium: ['warn', 'info'],
  high: ['serious', 'alert'],
  critical: ['critical', 'flame'],
};

export const riskIcon = (risk: Risk): IconName => RISK_STYLE[risk]?.[1] ?? 'info';

export function RiskBadge({ risk, size, withPrefix }: { risk: Risk | string | null | undefined; size?: 'sm' | 'lg'; withPrefix?: boolean }) {
  const { t, tx } = useI18n();
  if (!risk) return <Badge tone="neutral">{t('app.none')}</Badge>;
  const [tone, icon] = RISK_STYLE[risk as Risk] ?? ['neutral', 'info'];
  const label = tx(`risk.${risk}`, risk);
  return (
    <Badge tone={tone} icon={icon} size={size}>
      {withPrefix ? t('risk.withLabel', { risk: label }) : label}
    </Badge>
  );
}

const STATUS_STYLE: Record<ApprovalStatus, [Tone, IconName]> = {
  pending: ['warn', 'clock'],
  approved: ['allow', 'check-circle'],
  denied: ['deny', 'x-octagon'],
  expired: ['neutral', 'clock'],
  cancelled: ['neutral', 'x-circle'],
};

export function ApprovalStatusBadge({ status }: { status: ApprovalStatus | string }) {
  const { tx } = useI18n();
  const [tone, icon] = STATUS_STYLE[status as ApprovalStatus] ?? ['neutral', 'info'];
  return (
    <Badge tone={tone} icon={icon}>
      {tx(`status.${status}`, status)}
    </Badge>
  );
}

const LABEL_STYLE: Record<DetectionLabel, [Tone, IconName]> = {
  benign: ['allow', 'shield-check'],
  suspicious: ['warn', 'eye'],
  injection: ['deny', 'shield-alert'],
};

export function DetectionLabelBadge({ label, size }: { label: DetectionLabel | string; size?: 'sm' | 'lg' }) {
  const { tx } = useI18n();
  const [tone, icon] = LABEL_STYLE[label as DetectionLabel] ?? ['neutral', 'info'];
  return (
    <Badge tone={tone} icon={icon} size={size}>
      {tx(`label.${label}`, label)}
    </Badge>
  );
}

const LAYER_ICON: Record<Layer, IconName> = {
  policy: 'file-text',
  ratelimit: 'clock',
  taint: 'layers',
  detector: 'eye',
  approval: 'user',
  system: 'settings',
};

/** Layer chip: each defence layer gets a distinct hue, icon and name. */
export function LayerChip({ layer }: { layer: Layer | string }) {
  const { tx } = useI18n();
  const known = (['policy', 'ratelimit', 'taint', 'detector', 'approval', 'system'] as string[]).includes(layer);
  return (
    <span className={`chip chip--layer chip--${known ? layer : 'system'}`}>
      <Icon name={LAYER_ICON[layer as Layer] ?? 'info'} size={14} strokeWidth={2.2} />
      <span>{tx(`layer.${layer}`, layer)}</span>
    </span>
  );
}
