package cloudgraph

import "embed"

// ChartFS exports the embedded Helm chart files.
//
//go:embed all:deployments/helm/cloudgraph
var ChartFS embed.FS
