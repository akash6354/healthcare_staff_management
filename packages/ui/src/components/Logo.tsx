/** Brand marks copied from /media at build time (scripts/copy-brand.mjs); originals are never modified. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <img src="/brand/icon-192.png" width={size} height={size} alt="" className="rounded-[22%]" />
  );
}

export function Wordmark({ onDark = false, height = 28 }: { onDark?: boolean; height?: number }) {
  return (
    <img
      src={onDark ? '/brand/oglos-logo-dark.png' : '/brand/oglos-logo-light.png'}
      height={height}
      style={{ height, width: 'auto' }}
      className="block max-w-none shrink-0 self-start"
      alt="OGLOS"
    />
  );
}
