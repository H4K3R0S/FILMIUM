import { Database, type LucideIcon } from "lucide-react";

import type { FilmiumLibraryStatisticsValue } from "./libraryStatistics";


type StatisticCardProps = {
  icon?: LucideIcon;
  label: string;
  tone?: string;
  value: number;
};


function StatisticCard({
  icon: Icon,
  label,
  tone = "purple",
  value,
}: StatisticCardProps) {
  return (
    <div className={`filmium-library-stat tone-${tone}`}>
      {Icon && <Icon />}
      <strong>{value.toLocaleString("sr")}</strong>
      <span>{label}</span>
    </div>
  );
}


/**
 * Prikazuje pregled dostupnosti sadržaja iz poslednjeg skeniranja.
 */
export default function FilmiumLibraryStatistics({
  statistics,
}: {
  statistics: FilmiumLibraryStatisticsValue;
}) {
  return (
    <div className="filmium-library-statistics">
      <StatisticCard
        icon={Database}
        label="sadržaja"
        value={statistics.total}
      />
      <StatisticCard
        label="dostupno"
        tone="green"
        value={statistics.available}
      />
      <StatisticCard
        label="nedostupno"
        tone="yellow"
        value={statistics.unavailable}
      />
      <StatisticCard
        label="bez video-fajla"
        tone="red"
        value={statistics.catalogOnly}
      />
      <StatisticCard
        label="zahteva pažnju"
        tone="orange"
        value={statistics.attention}
      />
    </div>
  );
}
