#ifndef SIM_FAIR_H
#define SIM_FAIR_H

#include "deck.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

py::tuple
simulate_fair_cpp(int users, int runs_per_user,
                  std::map<int, std::tuple<double, double, double>> prob,
                  int seed);

#endif // SIM_FAIR_H
