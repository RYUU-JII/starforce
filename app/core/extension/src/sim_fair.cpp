#include "sim_fair.h"

py::tuple
simulate_fair_cpp(int users, int runs_per_user,
                  std::map<int, std::tuple<double, double, double>> prob,
                  int seed) {

  std::vector<SimResult> all_results;
  all_results.reserve(users * runs_per_user);

  std::mt19937 rng(seed);
  std::uniform_real_distribution<double> dist(0.0, 1.0);

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

      while (curr < 22 && clicks_run < 5000) {
        clicks_run++;
        res.cost += get_cost_200(curr);

        double p_s = std::get<0>(prob[curr]);
        double p_b = std::get<2>(prob[curr]);

        // IID Draw
        double val = dist(rng);
        int token = F;
        if (val < p_s)
          token = S;
        else if (val < p_s + (1.0 - p_s - p_b))
          token = F; // Fail range
        else
          token = B;

        int idx = curr - 12;
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
          // No drop on fail for Fair world either, per user request
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

  // Fair simulation doesn't use decks, so stats are 0
  return py::make_tuple(all_results, 0, 0, 0);
}
