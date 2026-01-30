#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "src/deck.h"
#include "src/sim_fair.h"
#include "src/sim_markov.h"
#include "src/sim_rigged.h"
#include "src/sim_sticky.h"


namespace py = pybind11;

PYBIND11_MODULE(starforce_sim_core, m) {
  py::class_<RunDeckConfig>(m, "RunDeckConfig")
      .def(py::init<>())
      .def_readwrite("chunk_size", &RunDeckConfig::chunk_size)
      .def_readwrite("chunk_size_by_level", &RunDeckConfig::chunk_size_by_level)
      .def_readwrite("wrap_random", &RunDeckConfig::wrap_random)
      .def_readwrite("corr_length_s", &RunDeckConfig::corr_length_s)
      .def_readwrite("corr_length_f", &RunDeckConfig::corr_length_f)
      .def_readwrite("corr_length_b", &RunDeckConfig::corr_length_b)
      .def_readwrite("tail_strength_s", &RunDeckConfig::tail_strength_s)
      .def_readwrite("tail_strength_f", &RunDeckConfig::tail_strength_f)
      .def_readwrite("tail_strength_b", &RunDeckConfig::tail_strength_b)
      .def_readwrite("cap_s", &RunDeckConfig::cap_s)
      .def_readwrite("cap_f", &RunDeckConfig::cap_f)
      .def_readwrite("cap_b", &RunDeckConfig::cap_b)
      .def_readwrite("box_size", &RunDeckConfig::box_size)
      .def_readwrite("mix_rate", &RunDeckConfig::mix_rate)
      .def_readwrite("mix_corr_mult", &RunDeckConfig::mix_corr_mult)
      .def_readwrite("mix_tail_mult", &RunDeckConfig::mix_tail_mult)
      .def_readwrite("mix_cap_mult", &RunDeckConfig::mix_cap_mult)
      .def_readwrite("anti_cluster_mode", &RunDeckConfig::anti_cluster_mode)
      .def_readwrite("fixed_length_mode", &RunDeckConfig::fixed_length_mode);

  py::class_<SimResult>(m, "SimResult")
      .def(py::init<>())
      .def_readwrite("streaks", &SimResult::streaks)
      .def_readwrite("b_streaks", &SimResult::b_streaks)
      .def_readwrite("lvl_stats", &SimResult::lvl_stats)
      .def_readwrite("cost", &SimResult::cost)
      .def_readwrite("clicks", &SimResult::clicks);

  m.def("simulate_rigged_cpp", &simulate_rigged_cpp,
        "Simulate with Rigged Decks (C++)", py::arg("users"),
        py::arg("runs_per_user"), py::arg("prob"), py::arg("config"),
        py::arg("start_mode") = "carry", py::arg("seed") = 42,
        py::arg("sequential") = false);

  m.def("simulate_sticky_cpp", &simulate_sticky_cpp,
        "Simulate with Sticky RNG (Cluster Decks)", py::arg("users"),
        py::arg("runs_per_user"), py::arg("prob"), py::arg("rho"),
        py::arg("seed") = 42, py::arg("sequential") = false);

  m.def("simulate_markov_cpp", &simulate_markov_cpp,
        "Simulate with Markov Chain Engine", py::arg("users"),
        py::arg("runs_per_user"), py::arg("prob"), py::arg("rho"),
        py::arg("seed") = 42);

  m.def("simulate_fair_cpp", &simulate_fair_cpp, "Simulate Fair World (IID)",
        py::arg("users"), py::arg("runs_per_user"), py::arg("prob"),
        py::arg("seed") = 42);
}
