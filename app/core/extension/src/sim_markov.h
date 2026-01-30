#ifndef SIM_MARKOV_H
#define SIM_MARKOV_H

#include "deck.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

py::tuple
simulate_markov_cpp(int users, int runs_per_user,
                    std::map<int, std::tuple<double, double, double>> prob,
                    double rho, int seed);

#endif // SIM_MARKOV_H
