import { AnimalMascot } from "./AnimalMascot";

/** Fully-drawn, static pig mascot — the finished frame of the loader's drawing. */
export function PigMascot({
  size = 56,
  bob = true,
  className,
}: {
  size?: number;
  bob?: boolean;
  className?: string;
}) {
  return <AnimalMascot animal="pig" size={size} bob={bob} className={className} />;
}
