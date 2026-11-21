export type Outcome = "H" | "D" | "A";

export type Forecast = {
  p_home: number;
  p_draw: number;
  p_away: number;
  p_over25: number;
  p_btts: number;
  over15: number | null;
  exp_total: number | null;
  xg_home: number | null;
  xg_away: number | null;
  model?: string;
  pick: Outcome;
  pick_prob: number;
  lead_points?: number;
  trained_through?: string | null;
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

export type ValidationStatus = "validated" | "experimental" | "unavailable";

export type MarketValidation = {
  n: number;
  model_loss: number | null;
  baseline_loss: number | null;
  status: ValidationStatus;
};

export type SeasonCornerAverage = {
  matches: number;
  corners_for: number | null;
  corners_against: number | null;
  total_per_match: number | null;
};

export type SeasonCornerAverages = {
  home_team: SeasonCornerAverage | null;
  away_team: SeasonCornerAverage | null;
};

export type CornerH2H = {
  meetings: number;
  corners_for_home_team: number | null;
  corners_for_away_team: number | null;
  total_per_match: number | null;
  list: Array<{ date: string; home: string; away: string; corners: string }>;
};

export type Corners = {
  available: boolean;
  reason?: string;
  expected?: { home: number; away: number; total: number };
  total_over?: Record<string, number>;
  team_over?: {
    home: Record<string, number>;
    away: Record<string, number>;
  };
  season_average?: SeasonCornerAverages | null;
  h2h?: CornerH2H | null;
  validation?: MarketValidation | null;
};

export type CorrectScore = {
  top: Array<{ score: string; p: number }>;
  grid: number[][];
  grid_note: string;
  grid_other: number | null;
};

export type MatchContext = {
  form_home: string[];
  form_away: string[];
  h2h: Array<{
    date: string;
    home: string;
    away: string;
    score: string;
    home_goals: number;
    away_goals: number;
    fixture_outcome: Outcome;
  }>;
  season_ppg_home: number | null;
  season_ppg_away: number | null;
  league_gpm: number | null;
};

/** The shape returned by GET /api/matches/{id}. */
export type MatchDetails = {
  id: number;
  competition: {
    code: string;
    name: string;
    stage: string | null;
    emblem_url: string | null;
    kind: string;
  };
  kickoff_utc: string;
  home: { name: string; badge_url: string | null };
  away: { name: string; badge_url: string | null };
  neutral: boolean;
  forecast: Forecast | null;
  goals: {
    exp_home: number | null;
    exp_away: number | null;
    exp_total: number | null;
    over: Record<string, number>;
    btts: number | null;
  };
  correct_score: CorrectScore;
  corners: Corners;
  validation: Record<string, MarketValidation | null>;
  flags: Array<{ side: string; type: string; days: number }>;
  result: MatchResult | null;
  context: MatchContext;
  note: string | null;
};

export type MatchesResponse = {
  date: string;
  matches: Match[];
  leagues: Array<{ code: string; name: string; emblem_url: string | null }>;
};

export type DateAvailability = {
  date: string;
  total: number;
  by_competition: Record<string, number>;
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
  spread_calibration: Array<{ from: number; to: number; n: number; confidence: number; hit_rate: number; range?: string }>;
  comparison: Array<{ model: string; n: number; logloss: number; pick_rate: number | null }>;
  leagues: Array<{ league: string; league_name: string; n: number; goals_per_match: number }>;
};
