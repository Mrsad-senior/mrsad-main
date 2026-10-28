import { useI18n } from '../i18n';

const ZONE_KEY = { low: 'gauge.low', flag: 'gauge.flag', block: 'gauge.block' } as const;

/**
 * Semicircular score meter (0..1). The zone (low/flag/block) is carried by colour
 * AND by tick marks at the thresholds AND by the numeric value, never colour alone.
 */
export function ScoreGauge({
  value,
  label,
  flagAt = 0.5,
  blockAt = 0.8,
  size = 180,
}: {
  value: number;
  label: string;
  flagAt?: number;
  blockAt?: number;
  size?: number;
}) {
  const { fmtNumber, t } = useI18n();
  const v = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  const zone = v >= blockAt ? 'block' : v >= flagAt ? 'flag' : 'low';
  const r = 80;
  const cx = 100;
  const cy = 96;
  // Angles run from 180deg (left, 0) to 0deg (right, 1). The gauge always fills
  // left-to-right: it is a quantity scale, which is not mirrored in RTL.
  const point = (frac: number, radius = r) => {
    const angle = Math.PI * (1 - frac);
    return [cx + radius * Math.cos(angle), cy - radius * Math.sin(angle)] as const;
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = point(from);
    const [x2, y2] = point(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 0.5 ? 1 : 0} 1 ${x2} ${y2}`;
  };
  const tick = (frac: number) => {
    const [x1, y1] = point(frac, r - 16);
    const [x2, y2] = point(frac, r + 9);
    return `M ${x1} ${y1} L ${x2} ${y2}`;
  };
  const display = fmtNumber(v, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

  return (
    <div className={`gauge gauge--${zone}`} style={{ inlineSize: size }} dir="ltr">
      <svg
        viewBox="0 0 200 112"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(v.toFixed(3))}
        aria-valuetext={`${display} (${t(ZONE_KEY[zone])})`}
      >
        <path d={arc(0, 1)} className="gauge__track" />
        {v > 0.001 ? <path d={arc(0, v)} className="gauge__fill" /> : null}
        <path d={tick(flagAt)} className="gauge__tick" />
        <path d={tick(blockAt)} className="gauge__tick" />
        <text x={cx} y={cy - 14} textAnchor="middle" className="gauge__value">
          {display}
        </text>
      </svg>
      <div className="gauge__zone">{t(ZONE_KEY[zone])}</div>
    </div>
  );
}
