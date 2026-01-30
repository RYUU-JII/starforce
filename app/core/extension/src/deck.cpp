#include "deck.h"

long long get_cost_200(int level) {
  static const std::map<int, long long> COST = {
      {12, 34300000LL},  {13, 55000000LL},  {14, 95000000LL},
      {15, 72400000LL},  {16, 100000000LL}, {17, 130400000LL},
      {18, 324700000LL}, {19, 584300000LL}, {20, 148000000LL},
      {21, 272200000LL}};
  auto it = COST.find(level);
  if (it != COST.end())
    return it->second;
  return 0;
}

// ClusterDeck Implementation
ClusterDeck::ClusterDeck(int s_cnt, int f_cnt, int b_cnt,
                         double clumping_factor, int seed)
    : rng(seed), rho(clumping_factor) {
  if (s_cnt < 0)
    s_cnt = 0;
  if (f_cnt < 0)
    f_cnt = 0;
  if (b_cnt < 0)
    b_cnt = 0;

  deck.reserve(s_cnt + f_cnt + b_cnt);
  int total = s_cnt + f_cnt + b_cnt;
  if (total == 0)
    return;

  int rem_s = s_cnt;
  int rem_f = f_cnt;
  int rem_b = b_cnt;

  std::uniform_real_distribution<double> dist(0.0, 1.0);
  int prev_token = -1;
  double bias_mult = 1.0 + (rho * 100.0);

  for (int i = 0; i < total; ++i) {
    double w_s = (double)rem_s;
    double w_f = (double)rem_f;
    double w_b = (double)rem_b;

    if (prev_token != -1) {
      if (prev_token == S)
        w_s *= bias_mult;
      else if (prev_token == F)
        w_f *= bias_mult;
      else if (prev_token == B)
        w_b *= bias_mult;
    }

    double w_total = w_s + w_f + w_b;
    double val = dist(rng) * w_total;

    int picked = -1;
    if (val < w_s) {
      picked = S;
      rem_s--;
    } else if (val < w_s + w_f) {
      picked = F;
      rem_f--;
    } else {
      picked = B;
      rem_b--;
    }

    deck.push_back(picked);
    prev_token = picked;
  }
}

int ClusterDeck::draw() {
  if (deck.empty())
    return F;
  if (idx >= deck.size())
    idx = 0;
  return deck[idx++];
}

// RunDeck Implementation
RunDeck::RunDeck(int s, int f, int b, RunDeckConfig cfg, int seed)
    : s_cnt(s), f_cnt(f), b_cnt(b), config(cfg), rng(seed) {
  _build();
}

void RunDeck::_build() {
  int total = s_cnt + f_cnt + b_cnt;
  std::vector<std::pair<int, int>> seq;

  if (config.box_size <= 0 || config.box_size >= total) {
    seq = _build_block_runs(
        s_cnt, f_cnt, b_cnt, config.corr_length_s, config.corr_length_f,
        config.corr_length_b, config.tail_strength_s, config.tail_strength_f,
        config.tail_strength_b, config.cap_s, config.cap_f, config.cap_b);
  } else {
    int remaining = total;
    int cur_s = s_cnt, cur_f = f_cnt, cur_b = b_cnt;
    std::vector<std::vector<std::pair<int, int>>> blocks;

    while (remaining > 0) {
      int size = std::min(remaining, config.box_size);
      int bs, bf, bb;
      _alloc_block_counts(size, cur_s, cur_f, cur_b, bs, bf, bb);

      blocks.push_back(_build_block_runs(
          bs, bf, bb, config.corr_length_s, config.corr_length_f,
          config.corr_length_b, config.tail_strength_s, config.tail_strength_f,
          config.tail_strength_b, config.cap_s, config.cap_f, config.cap_b));

      cur_s -= bs;
      cur_f -= bf;
      cur_b -= bb;
      remaining -= size;
    }

    std::shuffle(blocks.begin(), blocks.end(), rng);

    int prev_token = -1;
    for (auto &blk : blocks) {
      if (blk.empty())
        continue;
      if (prev_token != -1 && blk.size() > 1 && blk[0].first == prev_token) {
        std::swap(blk[0], blk[1]);
      }
      seq.insert(seq.end(), blk.begin(), blk.end());
      prev_token = seq.back().first;
    }
  }

  sequence = seq;
  idx = 0;
  offset = 0;
  builds++;

  total_len = 0;
  prefix_sum.clear();
  for (auto &p : sequence) {
    total_len += p.second;
    prefix_sum.push_back(total_len);
  }
}

std::vector<int> RunDeck::_sample_run_lengths(int count, double mean_len,
                                              double tail_strength, int cap) {
  std::vector<int> runs;
  if (count <= 0)
    return runs;

  int remaining = count;
  std::uniform_real_distribution<double> dist(0.0, 1.0);

  while (remaining > 0) {
    bool use_mix = (config.mix_rate > 0 && dist(rng) < config.mix_rate);
    double mean_used = mean_len * (use_mix ? config.mix_corr_mult : 1.0);
    mean_used = std::max(1.0, mean_used);
    double tail_used = tail_strength * (use_mix ? config.mix_tail_mult : 1.0);
    tail_used = std::min(1.0, std::max(0.0, tail_used));

    int cap_used = cap;
    if (cap_used > 0 && use_mix) {
      cap_used = (int)std::round(cap_used * config.mix_cap_mult);
    }

    int length = 0;

    if (tail_used <= 0) {
      if (config.fixed_length_mode) {
        int base = std::max(1, (int)std::floor(mean_used));
        int top = std::max(1, (int)std::ceil(mean_used));
        if (cap_used > 0) {
          base = std::min(base, cap_used);
          top = std::min(top, cap_used);
        }
        if (base >= top) {
          length = base;
        } else {
          double p_top = (mean_used - base) / (double)(top - base);
          length = (dist(rng) < p_top) ? top : base;
        }
      } else {
        // Geometric Distribution for Mean Length
        // Mean of Geometric(p) is 1/p. So p = 1/mean.
        double p = 1.0 / mean_used;
        std::geometric_distribution<int> geom(p);
        length = geom(rng) + 1;
      }
    } else {
      double p = 1.0 / mean_used;
      if (dist(rng) < tail_used) {
        int tail_min = std::max(2, (int)(mean_used * 2));
        int tail_max = std::max(tail_min, (int)(mean_used * 4));
        if (cap_used > 0)
          tail_max = std::min(tail_max, cap_used);

        if (tail_min >= tail_max)
          length = tail_min;
        else {
          std::uniform_int_distribution<int> tail_dist(tail_min, tail_max);
          length = tail_dist(rng);
        }
      } else {
        std::geometric_distribution<int> geom(p);
        length = geom(rng) + 1;
      }
    }

    if (cap_used > 0)
      length = std::min(length, cap_used);
    if (length > remaining)
      length = remaining;

    runs.push_back(length);
    remaining -= length;
  }

  std::shuffle(runs.begin(), runs.end(), rng);
  return runs;
}

std::vector<std::pair<int, int>>
RunDeck::_build_block_runs(int s, int f, int b, double cs, double cf, double cb,
                           double ts, double tf, double tb, int caps, int capf,
                           int capb) {

  auto s_runs = _sample_run_lengths(s, cs, ts, caps);
  auto f_runs = _sample_run_lengths(f, cf, tf, capf);
  auto b_runs = _sample_run_lengths(b, cb, tb, capb);

  std::vector<std::pair<int, int>> all_runs;
  all_runs.reserve(s_runs.size() + f_runs.size() + b_runs.size());

  int r_s = s, r_f = f, r_b = b;
  int max_ops = s_runs.size() + f_runs.size() + b_runs.size();
  int idx_s = 0, idx_f = 0, idx_b = 0;
  std::uniform_real_distribution<double> dist(0.0, 1.0);
  int prev_type = -1;

  for (int k = 0; k < max_ops; k++) {
    std::vector<int> candidates;
    if (idx_s < s_runs.size())
      candidates.push_back(S);
    if (idx_f < f_runs.size())
      candidates.push_back(F);
    if (idx_b < b_runs.size())
      candidates.push_back(B);

    if (candidates.empty())
      break;

    if (config.anti_cluster_mode && prev_type != -1 && candidates.size() > 1) {
      auto it = std::find(candidates.begin(), candidates.end(), prev_type);
      if (it != candidates.end())
        candidates.erase(it);
    }

    int chosen = -1;
    double w_sum = 0;
    std::vector<double> weights;
    for (int t : candidates) {
      double w = (t == S) ? r_s : (t == F ? r_f : r_b);
      weights.push_back(w);
      w_sum += w;
    }

    if (w_sum <= 0) {
      std::uniform_int_distribution<int> u_dist(0, candidates.size() - 1);
      chosen = candidates[u_dist(rng)];
    } else {
      double r = dist(rng) * w_sum;
      double acc = 0;
      for (size_t i = 0; i < candidates.size(); i++) {
        acc += weights[i];
        if (r < acc) {
          chosen = candidates[i];
          break;
        }
      }
      if (chosen == -1)
        chosen = candidates.back();
    }

    int length = 0;
    if (chosen == S) {
      length = s_runs[idx_s++];
      r_s -= length;
    } else if (chosen == F) {
      length = f_runs[idx_f++];
      r_f -= length;
    } else {
      length = b_runs[idx_b++];
      r_b -= length;
    }

    all_runs.push_back({chosen, length});
    prev_type = chosen;
  }
  return all_runs;
}

void RunDeck::_alloc_block_counts(int size, int rem_s, int rem_f, int rem_b,
                                  int &out_s, int &out_f, int &out_b) {
  long long total = (long long)rem_s + rem_f + rem_b;
  if (total <= 0) {
    out_s = 0;
    out_f = 0;
    out_b = 0;
    return;
  }
  out_s = (int)std::round((double)size * rem_s / total);
  out_b = (int)std::round((double)size * rem_b / total);
  out_f = size - out_s - out_b;

  if (out_s > rem_s)
    out_s = rem_s;
  if (out_b > rem_b)
    out_b = rem_b;
  out_f = size - out_s - out_b;

  if (out_f > rem_f) {
    int excess = out_f - rem_f;
    int reduce_s = std::min(excess, out_s);
    out_s -= reduce_s;
    excess -= reduce_s;
    if (excess > 0) {
      int reduce_b = std::min(excess, out_b);
      out_b -= reduce_b;
    }
    out_f = size - out_s - out_b;
  }
}

void RunDeck::jump_random() {
  if (sequence.empty() || total_len <= 0)
    return;
  std::uniform_int_distribution<int> d(0, total_len - 1);
  int pos = d(rng);

  auto it = std::upper_bound(prefix_sum.begin(), prefix_sum.end(), pos);
  int i = (int)(it - prefix_sum.begin());
  if (i >= (int)sequence.size())
    i = sequence.size() - 1;

  int prev_end = (i > 0) ? prefix_sum[i - 1] : 0;
  idx = i;
  offset = pos - prev_end;
}

int RunDeck::draw() {
  if (sequence.empty())
    return S;
  if (idx >= (int)sequence.size()) {
    wraps++;
    if (config.wrap_random) {
      jump_random();
    } else {
      idx = 0;
      offset = 0;
    }
  }
  auto &p = sequence[idx];
  int token = p.first;
  draws++;
  offset++;
  if (offset >= p.second) {
    idx++;
    offset = 0;
  }
  return token;
}

// RunDeckManager Implementation
RunDeckManager::RunDeckManager(
    std::map<int, std::tuple<double, double, double>> p, RunDeckConfig c,
    int seed)
    : prob(p), config(c), rng(seed) {}

RunDeck *RunDeckManager::get_deck(int level) {
  if (decks.find(level) == decks.end()) {
    if (prob.find(level) == prob.end())
      return nullptr;

    auto &p = prob[level];
    int size = config.chunk_size;
    if (config.chunk_size_by_level.find(level) !=
        config.chunk_size_by_level.end()) {
      size = config.chunk_size_by_level[level];
    }

    double p_s = std::get<0>(p) + config.bias;
    p_s = std::max(
        0.0,
        std::min(0.99, p_s)); // Cap to avoid 100% success which breaks things

    int s_cnt = (int)std::round(size * p_s);
    int b_cnt = (int)std::round(size * std::get<2>(p));
    int f_cnt = size - s_cnt - b_cnt;

    int total = s_cnt + f_cnt + b_cnt;
    if (total != size)
      f_cnt += (size - total);

    std::uniform_int_distribution<int> sd(0, 1000000);
    decks[level] =
        std::make_unique<RunDeck>(s_cnt, f_cnt, b_cnt, config, sd(rng));

    if (randomize_on_create)
      decks[level]->jump_random();
  }
  return decks[level].get();
}

int RunDeckManager::draw(int level) {
  RunDeck *d = get_deck(level);
  if (!d)
    return S;
  return d->draw();
}

void RunDeckManager::start_run(std::string mode) {
  if (mode == "random") {
    for (auto &pair : decks) {
      pair.second->jump_random();
    }
    randomize_on_create = true;
  } else {
    randomize_on_create = false;
  }
}

std::tuple<int, int, int> RunDeckManager::stats() {
  int d = 0, b = 0, w = 0;
  for (auto &pair : decks) {
    d += pair.second->draws;
    b += pair.second->builds;
    w += pair.second->wraps;
  }
  return {d, b, w};
}
