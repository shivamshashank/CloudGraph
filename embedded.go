// Package cloudgraph lives at the module root (not under cmd/ or
// services/) because Go's //go:embed directive resolves its path relative
// to this file's own directory — it must sit next to deployments/helm at
// repo root to embed it. Do not relocate this file during doc/dir cleanups.
package cloudgraph

import "embed"

// ChartFS exports the embedded Helm chart files.
//
//go:embed all:deployments/helm/cloudgraph
var ChartFS embed.FS
