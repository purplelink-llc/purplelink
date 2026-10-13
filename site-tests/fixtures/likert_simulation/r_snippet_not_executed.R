library(latent2likert)

# Loadings, four items per construct, as in the Python example
lambda    <- c(0.80, 0.75, 0.70, 0.70, 0.85, 0.80, 0.75, 0.70)
construct <- rep(1:2, each = 4)

# Correlation between the latent variables behind each item:
# lambda_i * lambda_j * rho, with rho = 0.40 across constructs and 1 within
rho <- ifelse(outer(construct, construct, "=="), 1, 0.40)
R <- outer(lambda, lambda) * rho
diag(R) <- 1

set.seed(2026)
dat <- as.data.frame(rlikert(size = 500, n_items = 8, n_levels = 5, corr = R))
names(dat) <- c(paste0("TRUST", 1:4), paste0("INTENT", 1:4))
dat <- cbind(id = seq_len(nrow(dat)), dat, synthetic = TRUE)

write.csv(dat, "synthetic_trust_intent.csv", row.names = FALSE)
round(cor(dat[, 2:9]), 2)   # compare with R; expect some shrinkage
