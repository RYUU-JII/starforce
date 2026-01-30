#include "sim_rigged.h"

py::tuple
simulate_rigged_cpp(int users, int runs_per_user,
                    std::map<int, std::tuple<double, double, double>> prob,
                    RunDeckConfig config, std::string start_mode, int seed,
                    bool sequential) {

  std::vector<SimResult> all_results;
  all_results.reserve(users * runs_per_user);

  RunDeckManager manager(prob, config, seed);
  manager.start_run(start_mode);

  if (sequential) {
    for (int i = 0; i < users; ++i) {
      SimResult res;
      res.lvl_stats.resize(10, std::vector<int>(4, 0));
      res.cost = 0;
      res.clicks = 0;

      for (int r = 0; r < runs_per_user; ++r) {
        int curr = 12; // Start at 12
        int clicks_run = 0;
        int curr_type = -1;
        int curr_len = 0;

        while (curr < 22 && clicks_run < 5000) {
          clicks_run++;
          res.cost += get_cost_200(curr);

          int idx = curr - 12;
          int token = manager.draw(curr);

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

  } else {
    // Interleaved Loop
    std::vector<int> currs(users, 12);
    std::vector<int> clicks(users, 0);
    std::vector<long long> costs(users, 0);
    std::vector<int> runs_done(users, 0);
    std::vector<std::vector<std::vector<int>>> lvl_stats(
        users, std::vector<std::vector<int>>(10, std::vector<int>(4, 0)));

    std::vector<std::vector<int>> u_streaks(users);
    std::vector<std::vector<int>> u_b_streaks(users);
    std::vector<int> u_curr_type(users, -1);
    std::vector<int> u_curr_len(users, 0);

    int active = users;

    while (active > 0) {
      for (int i = 0; i < users; ++i) {
        if (runs_done[i] >= runs_per_user)
          continue;

        int curr = currs[i];
        costs[i] += get_cost_200(curr);
        clicks[i]++;

        int token = manager.draw(curr);

        int idx = curr - 12;
        if (idx >= 0 && idx < 10) {
          lvl_stats[i][idx][0]++;
          if (token == S)
            lvl_stats[i][idx][1]++;
          else if (token == F)
            lvl_stats[i][idx][2]++;
          else
            lvl_stats[i][idx][3]++;
        }

        int next = curr;
        if (token == S) {
          if (curr < 22)
            next++;
        } else if (token == B) {
          next = 12;
        } else if (token == F) {
          // No drop on fail
        }
        currs[i] = next;

        int type_code = (token == S) ? 0 : (token == F ? 1 : 2);
        if (type_code == u_curr_type[i]) {
          u_curr_len[i]++;
        } else {
          if (u_curr_len[i] > 0) {
            if (u_curr_type[i] == 0)
              u_streaks[i].push_back(u_curr_len[i]);
            else if (u_curr_type[i] == 1)
              u_streaks[i].push_back(-u_curr_len[i]);
            else
              u_b_streaks[i].push_back(u_curr_len[i]);
          }
          u_curr_type[i] = type_code;
          u_curr_len[i] = 1;
        }

        bool finished = (currs[i] >= 22 || clicks[i] >= 5000);

        if (finished) {
          if (u_curr_len[i] > 0) {
            if (u_curr_type[i] == 0)
              u_streaks[i].push_back(u_curr_len[i]);
            else if (u_curr_type[i] == 1)
              u_streaks[i].push_back(-u_curr_len[i]);
            else
              u_b_streaks[i].push_back(u_curr_len[i]);
          }

          SimResult res;
          res.streaks = u_streaks[i];
          res.b_streaks = u_b_streaks[i];
          res.lvl_stats = lvl_stats[i];
          res.cost = costs[i];
          res.clicks = clicks[i];
          all_results.push_back(res);

          runs_done[i]++;
          if (runs_done[i] < runs_per_user) {
            currs[i] = 12;
            clicks[i] = 0;
            costs[i] = 0;
            lvl_stats[i] =
                std::vector<std::vector<int>>(10, std::vector<int>(4, 0));
            u_streaks[i].clear();
            u_b_streaks[i].clear();
            u_curr_type[i] = -1;
            u_curr_len[i] = 0;
          } else {
            active--;
          }
        }
      }
    }
  }

  auto s = manager.stats();
  return py::make_tuple(all_results, std::get<0>(s), std::get<1>(s),
                        std::get<2>(s));
}
