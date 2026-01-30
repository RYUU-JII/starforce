#ifndef SIM_RIGGED_H
#define SIM_RIGGED_H

#include "deck.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

py::tuple
simulate_rigged_cpp(int users, int runs_per_user,
                    std::map<int, std::tuple<double, double, double>> prob,
                    RunDeckConfig config, std::string start_mode, int seed,
                    bool sequential);

#endif // SIM_RIGGED_H
