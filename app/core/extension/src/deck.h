#ifndef DECK_H
#define DECK_H

#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <random>
#include <string>
#include <tuple>
#include <vector>

// Constants
const int S = 0;
const int F = 1;
const int B = 2;

long long get_cost_200(int level);

struct RunDeckConfig {
  int chunk_size = 200000;
  std::map<int, int> chunk_size_by_level;
  bool wrap_random = true;
  double corr_length_s = 12.0;
  double corr_length_f = 12.0;
  double corr_length_b = 12.0;
  double tail_strength_s = 0.05;
  double tail_strength_f = 0.05;
  double tail_strength_b = 0.05;
  int cap_s = 0;
  int cap_f = 0;
  int cap_b = 0;
  int box_size = 0;
  double mix_rate = 0.0;
  double mix_corr_mult = 1.0;
  double mix_tail_mult = 1.0;
  double mix_cap_mult = 1.0;
  bool anti_cluster_mode = false;
  bool fixed_length_mode = true;
  double bias = 0.0;
};

struct SimResult {
  std::vector<int> streaks;
  std::vector<int> b_streaks;
  std::vector<std::vector<int>> lvl_stats;
  long long cost;
  int clicks;
};

class ClusterDeck {
  std::vector<int> deck;
  int idx = 0;
  std::mt19937 rng;
  double rho = 0.0;

public:
  ClusterDeck(int s_cnt, int f_cnt, int b_cnt, double clumping_factor,
              int seed);
  int draw();
};

class RunDeck {
public:
  int s_cnt, f_cnt, b_cnt;
  RunDeckConfig config;
  std::vector<std::pair<int, int>> sequence; // (type, length)
  int idx = 0;
  int offset = 0;
  int builds = 0;
  int wraps = 0;
  int draws = 0;
  std::mt19937 rng;
  std::vector<int> prefix_sum;
  int total_len = 0;

  RunDeck(int s, int f, int b, RunDeckConfig cfg, int seed);
  void _build();
  std::vector<int> _sample_run_lengths(int count, double mean_len,
                                       double tail_strength, int cap);
  std::vector<std::pair<int, int>>
  _build_block_runs(int s, int f, int b, double cs, double cf, double cb,
                    double ts, double tf, double tb, int caps, int capf,
                    int capb);
  void _alloc_block_counts(int size, int rem_s, int rem_f, int rem_b,
                           int &out_s, int &out_f, int &out_b);
  void jump_random();
  int draw();
};

class RunDeckManager {
  std::map<int, std::tuple<double, double, double>> prob;
  RunDeckConfig config;
  std::mt19937 rng;
  std::map<int, std::unique_ptr<RunDeck>> decks;
  bool randomize_on_create = false;

public:
  RunDeckManager(std::map<int, std::tuple<double, double, double>> p,
                 RunDeckConfig c, int seed);
  RunDeck *get_deck(int level);
  int draw(int level);
  void start_run(std::string mode);
  std::tuple<int, int, int> stats();
};

#endif // DECK_H
