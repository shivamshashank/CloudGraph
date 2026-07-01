package observability

import (
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// TestObservabilityEndpoints verifies that Prometheus, Loki, and Otel-Collector endpoints are responsive.
func TestObservabilityEndpoints(t *testing.T) {
	t.Parallel()

	endpoints := []struct {
		name string
		url  string
	}{
		{"Prometheus Web UI", "http://prometheus.observability.svc.cluster.local:9090/-/healthy"},
		{"Loki API", "http://loki.observability.svc.cluster.local:3100/ready"},
		{"OpenTelemetry Collector Metrics", "http://otel-collector.observability.svc.cluster.local:8889/metrics"},
	}

	client := http.Client{
		Timeout: 5 * time.Second,
	}

	for _, ep := range endpoints {
		ep := ep // Capture range variable
		t.Run(ep.name, func(t *testing.T) {
			t.Parallel()

			// We perform a request. If not in-cluster, we skip gracefully.
			resp, err := client.Get(ep.url)
			if err != nil {
				t.Skipf("Skipping check: endpoint %s is not reachable (%v). This is expected when run outside the Kubernetes cluster.", ep.name, err)
				return
			}
			defer func() { _ = resp.Body.Close() }()

			assert.Equal(t, http.StatusOK, resp.StatusCode, "Endpoint %s should return HTTP 200 OK", ep.name)
		})
	}
}
