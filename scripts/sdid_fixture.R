# Reference answer for tests/data/sdid_fixture.csv from the R package (run once; output is committed).
lib <- "C:/Users/migue/AppData/Local/R/win-library/4.6"
.libPaths(c(lib, .libPaths()))
library(synthdid)
m <- as.matrix(read.csv("tests/data/sdid_fixture.csv", header = FALSE))
n0 <- 40; t0 <- 60
est <- synthdid_estimate(m, n0, t0)
cat(sprintf("%.10f\n", as.numeric(est)), file = "tests/data/sdid_fixture_r.txt")
cat("R estimate:", as.numeric(est), "\n")
