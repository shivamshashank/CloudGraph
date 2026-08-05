# Contributing to CloudGraph

Thank you for your interest in contributing to **CloudGraph**! We are building a
one-command observability platform for Kubernetes, Linux VMs, and cloud
instances, and we welcome contributions from developers, DevOps engineers, and
SREs of all experience levels.

By participating in this project, you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## 🗺️ How Can I Contribute?

There are many ways to contribute:

- **Report Bugs:** Open an issue if something doesn't work as expected.
- **Propose Features:** Suggest new capabilities, more alert rules, or
  additional dashboards.
- **Submit Pull Requests:** Improve the CLI, optimize Kubernetes configs, fix
  bugs, or expand documentation.
- **Improve Docs:** Clarify guides, fix typos, or add tutorials.

---

## 🛠️ Development Setup

CloudGraph is written in **Go** and deploys resources using **Helm** and
**Kubernetes**.

### Prerequisites

To set up a local development environment, you will need:

- **Go** (version 1.21 or higher)
- **kubectl**
- **Helm**
- A Kubernetes cluster (e.g., via [kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/))
- **Multipass** (Highly recommended if you are developing on macOS, to easily
  simulate a Linux VM environment)

### Get the Code

1. Fork the CloudGraph repository on GitHub.
2. Clone your fork locally:

   ```bash
   git clone https://github.com/YOUR-USERNAME/CloudGraph.git
   cd CloudGraph
   ```

3. Add the upstream repository:

   ```bash
   git remote add upstream https://github.com/shivamshashank/CloudGraph.git
   ```

4. Install the pre-commit hooks to automatically lint your code:

   ```bash
   ./scripts/setup-hooks.sh
   ```

---

## 💻 Working on Code

### 1. Create a Branch

Always create a descriptive branch for your changes:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

CloudGraph follows a clean directory structure:

- `cmd/cloudgraph/`: The entry point for the Go command-line application.
- `internal/`: Subpackages representing core CLI commands, configurations,
  doctor checks, Helm logic, observability components, and alerts.
- `charts/`: The Helm charts bundled or managed by the CLI.
- `dashboards/`: Prebuilt Grafana JSON dashboards.

### 3. Formatting & Linting

Before committing, ensure your code complies with standard Go styling and lint
guidelines:

- **Format Code:**

  ```bash
  gofmt -w .
  ```

- **Run Vet:**

  ```bash
  go vet ./...
  ```

- **Run Linter:** (We use `golangci-lint`)

  ```bash
  golangci-lint run
  ```

### 4. Running Tests

We expect all code changes to be accompanied by appropriate unit tests or
integration tests:

- **Run all tests:**

  ```bash
  go test ./...
  ```

- **Run tests with coverage:**

  ```bash
  go test ./... -cover
  ```

- **Generate HTML coverage report:**

  ```bash
  go test ./... -coverprofile=coverage.out
  go tool cover -html=coverage.out
  ```

**Python (`services/api`)** — install `requirements-dev.txt` once, then:

```bash
cd services/api
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Full suite, serially — measured at ~32 minutes on this project's suite
.venv/bin/pytest tests/ -q

# Parallel across CPU cores — measured at ~18 minutes (-n auto) on the same
# suite, a real ~45% reduction, not just a theoretical one. A single slow
# test (the real 25-scenario x 6-baseline benchmark evaluation) sets a
# floor xdist can't parallelize away, so don't expect more than this.
.venv/bin/pytest tests/ -q -n auto
```

---

## 📝 Commit Guidelines

We recommend using [Conventional Commits](https://www.conventionalcommits.org/)
for clean, readable history:

- `feat: add Slack notification support`
- `fix: correct cluster detection logic in doctor command`
- `docs: update quick start instructions in README`
- `test: add unit tests for config parsing`
- `refactor: simplify Helm deployment logic`

---

## 🚀 Submitting a Pull Request

When your changes are ready, submit a Pull Request:

1. Push your branch to your fork:

   ```bash
   git push origin branch-name
   ```

2. Navigate to the
   [CloudGraph repository](https://github.com/shivamshashank/CloudGraph) on
   GitHub.
3. Click "New Pull Request" and select your fork's branch.
4. Fill out the Pull Request template completely, providing clear details on
   what you changed and how you tested it.
5. Address any reviewer feedback or CI build failures.

Once approved and passing CI, a project maintainer will merge your PR!
