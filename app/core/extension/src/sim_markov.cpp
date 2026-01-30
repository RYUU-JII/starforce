#include "sim_markov.h"

py::tuple
simulate_markov_cpp(int users, int runs_per_user,
                    std::map<int, std::tuple<double, double, double>> prob,
                    double rho, int seed) {

  std::vector<SimResult> all_results;
  all_results.reserve(users * runs_per_user);

  std::mt19937 rng(seed);
  std::uniform_real_distribution<double> dist(0.0, 1.0);

  // Transition Matrices
  std::map<int, std::vector<std::vector<double>>> transitions;

  for (auto const &[level, p_tuple] : prob) {
    double p_s = std::get<0>(p_tuple);
    double p_b = std::get<2>(p_tuple);
    double p_f = 1.0 - p_s - p_b;

    std::vector<double> pi = {p_s, p_f, p_b};
    // 0=S, 1=F, 2=B
    std::vector<std::vector<double>> T(3, std::vector<double>(3));

    // To prevent infinite loops (absorbing states), we cap the stickiness
    // especially for the failure state which can cause "Death Spirals"
    double effective_rho = rho;
    
    for (int i = 0; i < 3; ++i) {
      double row_sum = 0.0;
      for (int j = 0; j < 3; ++j) {
        double delta = (i == j) ? 1.0 : 0.0;
        
        // Capping rho for failure state (i=1) to prevent 100% fail lock
        double r = effective_rho;
        if (i == 1 && r > 0.8) r = 0.8; 

        double val = (1.0 - r) * pi[j] + r * delta;
        if (val < 0) val = 0;
        if (val > 1) val = 1;
        T[i][j] = val;
        row_sum += val;
      }
      if (row_sum > 0.000001) {
        for (int j = 0; j < 3; ++j)
          T[i][j] /= row_sum;
      } else {
        for (int j = 0; j < 3; ++j)
          T[i][j] = pi[j];
      }
    }
    transitions[level] = T;
  }

  for (int i = 0; i < users; ++i) {
    SimResult res;
    res.lvl_stats.resize(10, std::vector<int>(4, 0));
    res.cost = 0;
    res.clicks = 0;

    for (int r = 0; r < runs_per_user; ++r) {
      int curr = 12;
      int clicks_run = 0;
      int curr_type = -1;
      int curr_len = 0;
      int prev_token = -1;

      while (curr < 22 && clicks_run < 5000) {
        clicks_run++;
        res.cost += get_cost_200(curr);

        int idx = curr - 12;
        double p_s_eff, p_f_eff, p_b_eff;

        if (prev_token == -1) {
          p_s_eff = std::get<0>(prob[curr]);
          p_b_eff = std::get<2>(prob[curr]);
          p_f_eff = 1.0 - p_s_eff - p_b_eff;
        } else {
          const auto &T = transitions[curr];
          p_s_eff = T[prev_token][0];
          p_f_eff = T[prev_token][1];
          p_b_eff = T[prev_token][2];
        }

        double val = dist(rng);
        int token = F;
        if (val < p_s_eff)
          token = S;
        else if (val < p_s_eff + p_f_eff)
          token = F;
        else
          token = B;

        if (idx >= 0 && idx < 10) {
          res.lvl_stats[idx][0]++;
          if (token == S)
            res.lvl_stats[idx][1]++;
          else if (token == F)
            res.lvl_stats[idx][2]++;
          else
            res.lvl_stats[idx][3]++;
        }

        int next_curr = curr;
        if (token == S) {
          if (curr < 22)
            next_curr++;
        } else if (token == B) {
          next_curr = 12;
        } else if (token == F) {
          // No drop on fail
        }

        int type_code = (token == S) ? 0 : (token == F ? 1 : 2);
        if (type_code == curr_type) {
          curr_len++;
        } else {
          if (curr_len > 0) {
            if (curr_type == 0)
              res.streaks.push_back(curr_len);
            else if (curr_type == 1)
              res.streaks.push_back(-curr_len);
            else
              res.b_streaks.push_back(curr_len);
          }
          curr_type = type_code;
          curr_len = 1;
        }
        prev_token = type_code;
        curr = next_curr;
      }
      if (curr_len > 0) {
        if (curr_type == 0)
          res.streaks.push_back(curr_len);
        else if (curr_type == 1)
          res.streaks.push_back(-curr_len);
        else
          res.b_streaks.push_back(curr_len);
      }
      res.clicks += clicks_run;
    }
    all_results.push_back(res);
  }

  return py::make_tuple(all_results, 0, 0, 0);
}
