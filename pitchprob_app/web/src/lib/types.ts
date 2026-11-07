export type Outcome = "H" | "D" | "A";

export type Forecast = {
  p_home: number;
  p_draw: number;
  p_away: number;
  p_over25: number;
  p_btts: number;
  xg_home: number;
  xg_away: number;
  model: string;
  pick: Outcome;
  pick_prob: number;
};

export type MatchResult = {
  home_goals: number;
  away_goals: number;
  outcome: Outcome;
};

export type Match = {
  id: number;
  league: string;
  league_name: string;
  league_emblem_url: string | null;
  kickoff_utc: string;
  status: string;
  matchday: number | null;
  home: string;
  away: string;
  home_crest: string | null;
  away_crest: string | null;
  forecast: Forecast | null;
  result: MatchResult | null;
  pick_hit: boolean | null;
  flags: Array<{ side: string; type: string; days: number }>;
  note: string | null;
  updated_at: string;
};

export type MatchDetails = Match & {
  extras: {
    goal_lines: Record<string, number>;
    handicap: Array<{ line: number; win: number; push: number; lose: number }>;
    scorelines: Array<{ score: string; p: number }>;
    corners?: {
      exp_home: number;
      exp_away: number;
      total: Record<string, number>;
      home: Record<string, number>;
      away: Record<string, number>;
    };
    context: {
      form_home: string[];
      form_away: string[];
      h2h: Array<{ date: string; home: string; away: string; score: string }>;
      season_ppg_home: number | null;
      season_ppg_away: number | null;
      league_gpm: number | null;
    };
  };
};

export type MatchesResponse = {
  date: string;
  matches: Match[];
  leagues: Array<{ code: string; name: string; emblem_url: string | null }>;
};

export type ResultsDaysResponse = Array<{ date: string; n: number; hits: number }>;

export type ResultsResponse = {
  date: string;
  summary: { n: number; hits: number; accuracy: number | null };
  leagues: Array<{
    code: string;
    name: string;
    emblem_url: string | null;
    matches: Match[];
  }>;
};

export type InsightsResponse = {
  source: "live" | "backtest";
  available: boolean;
  n: number;
  note?: string;
  confidence: Array<{ from: number; to: number; n: number; confidence: number; hit_rate: number }>;
  thresholds: Array<{ from: number; to: number; n: number; hit_rate: number }>;
  calibration: Array<{ from: number; to: number; n: number; confidence: number; hit_rate: number }>;
  comparison: Array<{ model: string; n: number; logloss: number; pick_rate: number | null }>;
  leagues: Array<{ league: string; league_name: string; n: number; goals_per_match: number }>;
};
