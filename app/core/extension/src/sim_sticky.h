#ifndef SIM_STICKY_H
#define SIM_STICKY_H

#include "deck.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

py::tuple
simulate_sticky_cpp(int users, int runs_per_user,
                    std::map<int, std::tuple<double, double, double>> prob,
                    double rho, int seed, bool sequential);

#endif // SIM_STICKY_H
