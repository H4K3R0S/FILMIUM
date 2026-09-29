// ==========          FILMIUM SERIJE          ==========

export interface FilmiumSeriesEpisode {
  season_number: number;
  episode_number: number;
  title: string | null;
  video: string;
  source: string;
  subtitles: string[];
}

export interface FilmiumSeriesProbe {
  width: number | null;
  height: number | null;
  video_codec: string | null;
  frame_rate: number | null;
  audio_codec: string | null;
  audio_channels: number | null;
  duration_seconds: number | null;
  available: boolean;
}

export interface FilmiumSeriesSeason {
  season_number: number;
  episodes: FilmiumSeriesEpisode[];
}

export interface FilmiumSeriesArtwork {
  kind: string;
  season: number | null;
  file: string;
}

export interface FilmiumSeriesScan {
  title: string;
  relative_directory: string;
  poster: string | null;
  backdrop: string | null;
  seasons: FilmiumSeriesSeason[];
  warnings: string[];
  artwork: FilmiumSeriesArtwork[];
  extras: string[];
}

export interface FilmiumSeriesLibraryScan {
  series: FilmiumSeriesScan[];
}

export interface FilmiumTmdbSeries {
  matched: boolean;
  configured: boolean;
  tmdb_id: number | null;
  name: string | null;
  year: number | null;
  genres: string[];
  overview: string | null;
  rating: number | null;
  poster_url: string | null;
  backdrop_url: string | null;
  season_count: number | null;
}

export interface FilmiumTmdbEpisode {
  episode_number: number;
  name: string | null;
  overview: string | null;
  air_date: string | null;
  rating: number | null;
  still_url: string | null;
}

export interface FilmiumTmdbSeason {
  episodes: FilmiumTmdbEpisode[];
}

export interface FilmiumSeriesImportResult {
  media_id: number;
  series_title: string;
  target_directory: string;
  season_count: number;
  episode_count: number;
  created_media: boolean;
}
