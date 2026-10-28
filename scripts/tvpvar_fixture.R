# Reference total connectedness index for tests/data/tvpvar_fixture.csv (run once; output committed).
.libPaths(c("C:/Users/migue/AppData/Local/R/win-library/4.6", .libPaths()))
suppressMessages({library(ConnectednessApproach); library(zoo)})
x <- as.matrix(read.csv("tests/data/tvpvar_fixture.csv", header = FALSE))
colnames(x) <- paste0("s", 1:ncol(x))
z <- zoo(x, as.Date("2020-01-01") + 0:(nrow(x) - 1))
dca <- ConnectednessApproach(z, nlag = 1, nfore = 10, model = "TVP-VAR", connectedness = "Time",
  VAR_config = list(TVPVAR = list(kappa1 = 0.99, kappa2 = 0.99, prior = "UninformativePrior")))
write.table(data.frame(tci = as.numeric(dca$TCI)), "tests/data/tvpvar_fixture_r.csv", row.names = FALSE, col.names = FALSE)
cat("R TCI mean:", mean(dca$TCI), "n:", length(dca$TCI), "\n")
