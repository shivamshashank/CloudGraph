package main

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	cloudgraph "github.com/shivamshashank/CloudGraph"
)

type qdrantCollectionStatus struct {
	Name   string
	Status string
	Points int
}

var (
	commandExistsFunc            = commandExists
	checkInternetConnectionFunc  = checkInternetConnection
	getKubectlCurrentContextFunc = getKubectlCurrentContext
	getDeploymentStatusesFunc    = getDeploymentStatuses
	getIngressHostsFunc          = getIngressHosts
	qdrantCollectionSummaryFunc  = getQdrantCollectionSummary
)

func runCmd(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func runCmdInDir(dir, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func commandExists(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func checkKubectl() bool {
	printHeader("Checking for kubectl")
	if commandExistsFunc("kubectl") {
		printSuccess("kubectl found")
		return true
	}
	printError("kubectl not found")
	return false
}

func checkK8sCluster() bool {
	printHeader("Checking for Kubernetes cluster")
	if !commandExistsFunc("kubectl") {
		printError("kubectl is required to check cluster")
		return false
	}
	cmd := exec.Command("kubectl", "cluster-info")
	if err := cmd.Run(); err == nil {
		printSuccess("Kubernetes cluster detected")
		return true
	}
	printWarning("No Kubernetes cluster detected")
	return false
}

func ensureKubeconfig() {
	printHeader("Configuring kubeconfig for non-root access")

	homeDir := os.Getenv("HOME")
	if homeDir != "" {
		kubeDir := filepath.Join(homeDir, ".kube")
		_ = os.MkdirAll(kubeDir, 0755)
		adminConf := "/etc/kubernetes/admin.conf"
		if _, err := os.Stat(adminConf); err == nil {
			dest := filepath.Join(kubeDir, "config")
			if err := copyFile(adminConf, dest); err == nil {
				uid := os.Getuid()
				gid := os.Getgid()
				_ = os.Chown(dest, uid, gid)
			}
		}
	}

	sudoUser := os.Getenv("SUDO_USER")
	if sudoUser != "" && sudoUser != "root" {
		u, err := user.Lookup(sudoUser)
		if err == nil {
			userHome := u.HomeDir
			if userHome != "" {
				kubeDir := filepath.Join(userHome, ".kube")
				_ = os.MkdirAll(kubeDir, 0755)
				_ = runCmd("chown", fmt.Sprintf("%s:%s", u.Uid, u.Gid), kubeDir)

				adminConf := "/etc/kubernetes/admin.conf"
				if _, err := os.Stat(adminConf); err == nil {
					dest := filepath.Join(kubeDir, "config")
					if err := copyFile(adminConf, dest); err == nil {
						_ = runCmd("chown", fmt.Sprintf("%s:%s", u.Uid, u.Gid), dest)
						// Clear user's kubernetes cache to prevent stale API schema errors
						_ = os.RemoveAll(filepath.Join(kubeDir, "cache"))
						printSuccess(fmt.Sprintf("Configured kubectl access for user '%s' (no sudo needed)", sudoUser))
					}
				}
			}
		}
	}
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	if err != nil {
		return err
	}
	return out.Sync()
}

func installKubeadm() bool {
	printHeader("Kubernetes cluster not found")
	fmt.Println("Would you like to install Kubernetes using kubeadm?")
	fmt.Println("Options:")
	fmt.Println("  1) Install kubeadm + kubelet + kubectl locally")
	fmt.Println("  2) Skip and use existing cluster")
	fmt.Println("  3) Exit")

	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("Choose option (1-3): ")
		input, err := reader.ReadString('\n')
		if err != nil {
			return false
		}
		choice := strings.TrimSpace(input)
		switch choice {
		case "1":
			printInfo("Installing Kubernetes...")
			return installKubernetesLocal()
		case "2":
			printWarning("Skipping kubeadm installation")
			return false
		case "3":
			printInfo("Exiting...")
			os.Exit(0)
		default:
			printError("Invalid option")
		}
	}
}

func installKubernetesLocal() bool {
	switch goos := runtime.GOOS; goos {
	case "linux":
		printInfo("Linux detected - installing kubeadm cluster")
		return installKubeadmLinux()
	default:
		printError(fmt.Sprintf("Unsupported OS: %s. CloudGraph is only supported on Linux.", goos))
		os.Exit(1)
	}
	return false
}

func installKubeadmLinux() bool {
	printInfo("Installing system prerequisites (swap, sysctl, conntrack, containerd)...")

	// Disable swap
	_ = exec.Command("swapoff", "-a").Run()
	_ = runCmd("sed", "-i", "/swap/s/^/#/", "/etc/fstab")

	// Enable kernel modules
	_ = exec.Command("modprobe", "overlay").Run()
	_ = exec.Command("modprobe", "br_netfilter").Run()

	_ = os.WriteFile("/etc/modules-load.d/k8s.conf", []byte("overlay\nbr_netfilter\n"), 0644)
	sysctlConfig := `net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
`
	_ = os.WriteFile("/etc/sysctl.d/k8s.conf", []byte(sysctlConfig), 0644)
	_ = exec.Command("sysctl", "--system").Run()

	// Update and install system requirements
	_ = runCmd("apt-get", "update", "-y")
	_ = runCmd("apt-get", "install", "-y", "apt-transport-https", "ca-certificates", "curl", "gpg", "conntrack", "containerd")

	// Containerd config
	_ = os.MkdirAll("/etc/containerd", 0755)
	cDefault, err := exec.Command("containerd", "config", "default").Output()
	if err == nil {
		cConfig := strings.ReplaceAll(string(cDefault), "SystemdCgroup = false", "SystemdCgroup = true")
		_ = os.WriteFile("/etc/containerd/config.toml", []byte(cConfig), 0644)
	}
	_ = exec.Command("systemctl", "restart", "containerd").Run()
	_ = exec.Command("systemctl", "enable", "containerd").Run()

	// Add Kubernetes repo
	_ = os.MkdirAll("/etc/apt/keyrings", 0755)
	resp, err := http.Get("https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key")
	if err == nil {
		defer resp.Body.Close()
		gpgCmd := exec.Command("gpg", "--yes", "--dearmor", "-o", "/etc/apt/keyrings/kubernetes-apt-keyring.gpg")
		gpgCmd.Stdin = resp.Body
		_ = gpgCmd.Run()
	}

	_ = os.WriteFile("/etc/apt/sources.list.d/kubernetes.list", []byte("deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /\n"), 0644)

	_ = runCmd("apt-get", "update", "-y")
	_ = runCmd("apt-get", "install", "-y", "kubeadm", "kubelet", "kubectl")
	_ = exec.Command("apt-mark", "hold", "kubeadm", "kubelet", "kubectl").Run()

	// Kubeadm config
	kubeadmConfig := `apiVersion: kubeadm.k8s.io/v1beta3
kind: InitConfiguration
---
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
networking:
  podSubnet: 10.244.0.0/16
---
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
conntrack:
  maxPerCore: 0
`
	_ = os.WriteFile("/tmp/kubeadm-config.yaml", []byte(kubeadmConfig), 0644)

	printInfo("Initializing Kubernetes cluster with conntrack configuration...")
	if err := runCmd("kubeadm", "init", "--config", "/tmp/kubeadm-config.yaml"); err != nil {
		printError("kubeadm init failed")
		return false
	}

	// Setup root kubeconfig
	homeDir := os.Getenv("HOME")
	if homeDir != "" {
		kubeDir := filepath.Join(homeDir, ".kube")
		_ = os.MkdirAll(kubeDir, 0755)
		_ = copyFile("/etc/kubernetes/admin.conf", filepath.Join(kubeDir, "config"))
		uid := os.Getuid()
		gid := os.Getgid()
		_ = os.Chown(filepath.Join(kubeDir, "config"), uid, gid)
	}

	printInfo("Installing Flannel CNI (v0.22.3)...")
	_ = runCmd("kubectl", "apply", "-f", "https://github.com/flannel-io/flannel/releases/download/v0.22.3/kube-flannel.yml")

	printInfo("Configuring master node...")
	_ = runCmd("kubectl", "taint", "nodes", "--all", "node-role.kubernetes.io/control-plane-")

	printInfo("Installing Rancher Local Path Provisioner...")
	_ = runCmd("kubectl", "apply", "-f", "https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml")
	_ = exec.Command("kubectl", "patch", "storageclass", "local-path", "-p", `{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}`).Run()

	printSuccess("Kubernetes cluster initialized")
	printInfo("Waiting for cluster to be ready...")
	time.Sleep(10 * time.Second)
	_ = runCmd("kubectl", "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=300s")
	return true
}

func ensureLocalStorage() {
	printHeader("Ensuring Local Storage Provisioner is installed")

	// Untaint control-plane nodes
	_ = exec.Command("kubectl", "taint", "nodes", "--all", "node-role.kubernetes.io/control-plane-").Run()
	_ = exec.Command("kubectl", "taint", "nodes", "--all", "node-role.kubernetes.io/master-").Run()

	// Check if local-path exists
	cmd := exec.Command("kubectl", "get", "storageclass", "local-path")
	if err := cmd.Run(); err != nil {
		printInfo("Rancher Local Path Provisioner not found. Installing...")
		_ = runCmd("kubectl", "apply", "-f", "https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml")
		_ = exec.Command("kubectl", "patch", "storageclass", "local-path", "-p", `{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}`).Run()
	} else {
		printSuccess("Rancher Local Path Provisioner is already installed")
	}
}

func ensureIngressController() {
	printHeader("Ensuring Ingress Controller is installed")

	cmd := exec.Command("kubectl", "get", "ns", "ingress-nginx")
	if err := cmd.Run(); err != nil {
		printInfo("NGINX Ingress Controller not found. Installing...")
		_ = runCmd("kubectl", "apply", "-f", "https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/baremetal/deploy.yaml")

		printInfo("Patching Ingress Controller to bind to host network ports 80/443...")
		time.Sleep(5 * time.Second)
		_ = exec.Command("kubectl", "patch", "deployment", "ingress-nginx-controller", "-n", "ingress-nginx",
			"--type=json", "-p", `[{"op": "add", "path": "/spec/template/spec/hostNetwork", "value": true}]`).Run()
	} else {
		printSuccess("NGINX Ingress Controller is already installed")
	}

	printInfo("Cleaning up Ingress validating webhook...")
	_ = exec.Command("kubectl", "delete", "validatingwebhookconfiguration", "ingress-nginx-admission", "--ignore-not-found=true").Run()
}

func checkHelm() {
	printHeader("Checking for Helm")
	if commandExists("helm") {
		cmd := exec.Command("helm", "version", "--short")
		out, _ := cmd.Output()
		printSuccess(fmt.Sprintf("helm found: %s", strings.TrimSpace(string(out))))
		return
	}
	printError("helm not found")
	installHelm()
}

func installHelm() {
	printInfo("Installing Helm...")
	if commandExists("curl") {
		getHelm, err := http.Get("https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3")
		if err != nil {
			printError(fmt.Sprintf("Failed to download Helm installer script: %v", err))
			os.Exit(1)
		}
		defer getHelm.Body.Close()

		bashCmd := exec.Command("bash")
		bashCmd.Stdin = getHelm.Body
		bashCmd.Stdout = os.Stdout
		bashCmd.Stderr = os.Stderr
		if err := bashCmd.Run(); err != nil {
			printError(fmt.Sprintf("Helm installation failed: %v", err))
			os.Exit(1)
		}
		printSuccess("Helm installed")
	} else {
		printError("curl is required to install Helm")
		os.Exit(1)
	}
}

func createNamespace() {
	printHeader("Preparing CloudGraph namespace")
	// Create namespace
	_ = exec.Command("kubectl", "create", "namespace", "cloudgraph-system", "--dry-run=client", "-o", "yaml").Run()
	// Apply namespace
	createCmd := exec.Command("kubectl", "create", "namespace", "cloudgraph-system")
	_ = createCmd.Run()

	printInfo("Configuring Helm ownership metadata on namespace...")
	_ = exec.Command("kubectl", "label", "namespace", "cloudgraph-system", "app.kubernetes.io/managed-by=Helm", "--overwrite").Run()
	_ = exec.Command("kubectl", "annotate", "namespace", "cloudgraph-system", "meta.helm.sh/release-name=cloudgraph", "--overwrite").Run()
	_ = exec.Command("kubectl", "annotate", "namespace", "cloudgraph-system", "meta.helm.sh/release-namespace=cloudgraph-system", "--overwrite").Run()

	printSuccess("Namespace 'cloudgraph-system' ready and configured for Helm")
}

func writeChartToTempDir() (string, error) {
	tempDir, err := os.MkdirTemp("", "cloudgraph-chart-*")
	if err != nil {
		return "", err
	}

	err = fs.WalkDir(cloudgraph.ChartFS, "deployments/helm/cloudgraph", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		relPath, err := filepath.Rel("deployments/helm/cloudgraph", path)
		if err != nil {
			return err
		}
		destPath := filepath.Join(tempDir, relPath)

		if d.IsDir() {
			return os.MkdirAll(destPath, 0755)
		}

		data, err := fs.ReadFile(cloudgraph.ChartFS, path)
		if err != nil {
			return err
		}

		return os.WriteFile(destPath, data, 0644)
	})

	if err != nil {
		_ = os.RemoveAll(tempDir)
		return "", err
	}

	return tempDir, nil
}

func installCloudGraph() {
	printHeader("Installing CloudGraph Core Stack")

	chartPath := "./deployments/helm/cloudgraph"
	isTemp := false
	var tempDir string

	if _, err := os.Stat(chartPath); err != nil {
		chartPath = "/home/shivam_shashank/CloudGraph/deployments/helm/cloudgraph"
	}

	if _, err := os.Stat(chartPath); err != nil {
		printInfo("Local Helm chart not found. Extracting embedded Helm chart...")
		var extractErr error
		tempDir, extractErr = writeChartToTempDir()
		if extractErr != nil {
			printError(fmt.Sprintf("Failed to extract embedded Helm chart: %v", extractErr))
			os.Exit(1)
		}
		chartPath = tempDir
		isTemp = true
	}

	printInfo(fmt.Sprintf("Using Helm chart from %s...", chartPath))
	printInfo("Updating and building Helm chart dependencies...")

	if err := runCmd("helm", "repo", "add", "neo4j", "https://helm.neo4j.com/neo4j"); err != nil {
		printError(fmt.Sprintf("Failed to add neo4j repo: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}
	if err := runCmd("helm", "repo", "add", "bitnami", "https://charts.bitnami.com/bitnami"); err != nil {
		printError(fmt.Sprintf("Failed to add bitnami repo: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}
	if err := runCmd("helm", "repo", "add", "qdrant", "https://qdrant.github.io/qdrant-helm"); err != nil {
		printError(fmt.Sprintf("Failed to add qdrant repo: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}
	if err := runCmd("helm", "repo", "update"); err != nil {
		printError(fmt.Sprintf("Failed to update helm repos: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}

	if err := runCmdInDir(chartPath, "helm", "dependency", "update"); err != nil {
		printError(fmt.Sprintf("Failed to update helm dependencies: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}
	if err := runCmdInDir(chartPath, "helm", "dependency", "build"); err != nil {
		printError(fmt.Sprintf("Failed to build helm dependencies: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}

	printInfo("Installing Helm chart...")
	if err := runCmdInDir(chartPath, "helm", "upgrade", "--install", "cloudgraph", ".", "--namespace", "cloudgraph-system", "--create-namespace"); err != nil {
		printError(fmt.Sprintf("Helm installation failed: %v", err))
		if isTemp {
			_ = os.RemoveAll(tempDir)
		}
		os.Exit(1)
	}

	if isTemp {
		_ = os.RemoveAll(tempDir)
	}
	printSuccess("CloudGraph deployed successfully")
}

func commandOutput(name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	out, err := cmd.Output()
	return strings.TrimSpace(string(out)), err
}

func httpGetJSON(url string) ([]byte, error) {
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 400 {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func parseQdrantCollectionPayload(payload []byte) ([]qdrantCollectionStatus, error) {
	var root struct {
		Result struct {
			Collections []struct {
				Name            string `json:"name"`
				Status          string `json:"status"`
				PointsCount     int    `json:"points_count"`
				PointsCountAlt  int    `json:"pointsCount"`
				VectorsCount    int    `json:"vectors_count"`
				VectorsCountAlt int    `json:"vectorsCount"`
				Count           int    `json:"count"`
			} `json:"collections"`
		} `json:"result"`
	}
	if err := json.Unmarshal(payload, &root); err != nil {
		return nil, err
	}

	collections := make([]qdrantCollectionStatus, 0, len(root.Result.Collections))
	for _, item := range root.Result.Collections {
		points := item.PointsCount
		if points == 0 {
			points = item.PointsCountAlt
		}
		if points == 0 {
			points = item.VectorsCount
		}
		if points == 0 {
			points = item.VectorsCountAlt
		}
		if points == 0 {
			points = item.Count
		}
		collections = append(collections, qdrantCollectionStatus{
			Name:   item.Name,
			Status: strings.ToLower(strings.TrimSpace(item.Status)),
			Points: points,
		})
	}
	return collections, nil
}

func probeQdrantCollections(baseURL string) ([]qdrantCollectionStatus, error) {
	payload, err := httpGetJSON(baseURL + "/collections")
	if err != nil {
		return nil, err
	}

	var listRoot struct {
		Result struct {
			Collections []struct {
				Name string `json:"name"`
			} `json:"collections"`
		} `json:"result"`
	}
	if err := json.Unmarshal(payload, &listRoot); err != nil {
		return nil, err
	}

	var collections []qdrantCollectionStatus
	for _, col := range listRoot.Result.Collections {
		colPayload, err := httpGetJSON(baseURL + "/collections/" + col.Name)
		if err != nil {
			// Fallback if details query fails
			collections = append(collections, qdrantCollectionStatus{
				Name:   col.Name,
				Status: "unknown",
				Points: 0,
			})
			continue
		}
		var detailRoot struct {
			Result struct {
				Status          string `json:"status"`
				PointsCount     int    `json:"points_count"`
				PointsCountAlt  int    `json:"pointsCount"`
				VectorsCount    int    `json:"vectors_count"`
				VectorsCountAlt int    `json:"vectorsCount"`
			} `json:"result"`
		}
		if err := json.Unmarshal(colPayload, &detailRoot); err == nil {
			status := strings.ToLower(strings.TrimSpace(detailRoot.Result.Status))
			if status == "" {
				status = "green"
			}
			points := detailRoot.Result.PointsCount
			if points == 0 {
				points = detailRoot.Result.PointsCountAlt
			}
			if points == 0 {
				points = detailRoot.Result.VectorsCount
			}
			if points == 0 {
				points = detailRoot.Result.VectorsCountAlt
			}
			collections = append(collections, qdrantCollectionStatus{
				Name:   col.Name,
				Status: status,
				Points: points,
			})
		} else {
			collections = append(collections, qdrantCollectionStatus{
				Name:   col.Name,
				Status: "unknown",
				Points: 0,
			})
		}
	}
	return collections, nil
}

func discoverQdrantService(namespace string) string {
	out, err := commandOutput("kubectl", "get", "svc", "-n", namespace, "--no-headers")
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		name := fields[0]
		if strings.Contains(name, "qdrant") {
			return name
		}
	}
	return ""
}

func getQdrantCollectionSummary(namespace string) []qdrantCollectionStatus {
	if !commandExistsFunc("kubectl") {
		return nil
	}
	if err := exec.Command("kubectl", "cluster-info").Run(); err != nil {
		return nil
	}

	serviceName := discoverQdrantService(namespace)
	if serviceName == "" {
		return nil
	}

	portForwardCmd := exec.Command("kubectl", "port-forward", "-n", namespace, fmt.Sprintf("svc/%s", serviceName), "6333:6333", "--address", "127.0.0.1")
	portForwardCmd.Stdout = io.Discard
	portForwardCmd.Stderr = io.Discard
	if err := portForwardCmd.Start(); err != nil {
		return nil
	}
	defer func() {
		_ = portForwardCmd.Process.Kill()
		_ = portForwardCmd.Wait()
	}()

	deadline := time.Now().Add(5 * time.Second)
	var collections []qdrantCollectionStatus
	var err error
	for time.Now().Before(deadline) {
		collections, err = probeQdrantCollections("http://127.0.0.1:6333")
		if err == nil && len(collections) > 0 {
			return collections
		}
		time.Sleep(300 * time.Millisecond)
	}

	return nil
}

func getTotalMemoryGB() float64 {
	if runtime.GOOS == "linux" {
		content, err := os.ReadFile("/proc/meminfo")
		if err != nil {
			return 0
		}
		for _, line := range strings.Split(string(content), "\n") {
			if strings.HasPrefix(line, "MemTotal:") {
				parts := strings.Fields(line)
				if len(parts) >= 2 {
					kb, err := strconv.ParseFloat(parts[1], 64)
					if err == nil {
						return kb / 1024.0 / 1024.0
					}
				}
			}
		}
	}
	return 0
}

func checkInternetConnection() bool {
	printHeader("Checking Internet connection")
	client := http.Client{Timeout: 6 * time.Second}
	resp, err := client.Get("https://www.google.com")
	if err != nil {
		printWarning("Internet connection not detected")
		return false
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 200 && resp.StatusCode < 400 {
		printSuccess("Internet connection")
		return true
	}
	printWarning("Internet connection appears unavailable")
	return false
}

func getKubectlCurrentContext() string {
	out, err := commandOutput("kubectl", "config", "current-context")
	if err != nil || out == "" {
		return "unknown"
	}
	return out
}

func getDeploymentStatuses(namespace string) map[string]string {
	statuses := map[string]string{}
	out, err := commandOutput("kubectl", "get", "deployments", "-n", namespace, "--no-headers")
	if err != nil {
		return statuses
	}
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		name := fields[0]
		ready := fields[1]
		if strings.Contains(ready, "/") {
			parts := strings.Split(ready, "/")
			if len(parts) == 2 && parts[0] == parts[1] && parts[0] != "0" {
				statuses[name] = "Running"
				continue
			}
		}
		statuses[name] = "Not Ready"
	}
	return statuses
}

func getIngressHosts(namespace string) []string {
	hosts := []string{}
	out, err := commandOutput("kubectl", "get", "ingress", "-n", namespace, "--no-headers", "-o", "custom-columns=HOST:.spec.rules[0].host")
	if err != nil {
		return hosts
	}
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || line == "<none>" {
			continue
		}
		hosts = append(hosts, line)
	}
	return hosts
}

func runDoctor() {
	printHeader("CloudGraph Doctor")

	printSuccess(fmt.Sprintf("OS: %s/%s", runtime.GOOS, runtime.GOARCH))
	checkInternetConnectionFunc()

	if commandExistsFunc("kubectl") {
		printSuccess("kubectl found")
	} else {
		printError("kubectl not found")
	}

	if commandExistsFunc("kubectl") && exec.Command("kubectl", "cluster-info").Run() == nil {
		printSuccess("Kubernetes cluster detected")
	} else {
		printWarning("Kubernetes cluster not detected")
	}

	if commandExists("helm") {
		out, err := commandOutput("helm", "version", "--short")
		if err == nil {
			printSuccess(fmt.Sprintf("Helm found: %s", out))
		} else {
			printSuccess("Helm found")
		}
	} else {
		printError("Helm not found")
	}

	memory := getTotalMemoryGB()
	if memory >= 4.0 {
		printSuccess("Minimum memory: 4GB+")
	} else {
		printWarning(fmt.Sprintf("Minimum memory: 4GB+ (detected %.2fGB)", memory))
	}

	cpuCount := runtime.NumCPU()
	if cpuCount >= 2 {
		printSuccess("Minimum CPU: 2 cores+")
	} else {
		printWarning(fmt.Sprintf("Minimum CPU: 2 cores+ (detected %d cores)", cpuCount))
	}

	qdrantCollections := qdrantCollectionSummaryFunc("cloudgraph-system")
	if len(qdrantCollections) > 0 {
		var summary []string
		for _, collection := range qdrantCollections {
			status := collection.Status
			if status == "" {
				status = "unknown"
			}
			if collection.Points > 0 {
				summary = append(summary, fmt.Sprintf("%s=%s(%d points)", collection.Name, status, collection.Points))
			} else {
				summary = append(summary, fmt.Sprintf("%s=%s", collection.Name, status))
			}
		}
		printSuccess(fmt.Sprintf("Qdrant reachable: %s", strings.Join(summary, ", ")))
	} else {
		printWarning("Qdrant not reachable or no collections reported yet")
	}

	fmt.Println("")
	printInfo("Run: sudo cloudgraph deploy")
}

func getPublicIP() string {
	client := &http.Client{Timeout: 3 * time.Second}
	// Try api.ipify.org
	resp, err := client.Get("https://api.ipify.org")
	if err == nil {
		defer resp.Body.Close()
		ipBytes, err := io.ReadAll(resp.Body)
		if err == nil {
			ip := strings.TrimSpace(string(ipBytes))
			if ip != "" {
				return ip
			}
		}
	}

	// Fallback to ifconfig.me
	resp, err = client.Get("https://ifconfig.me/ip")
	if err == nil {
		defer resp.Body.Close()
		ipBytes, err := io.ReadAll(resp.Body)
		if err == nil {
			ip := strings.TrimSpace(string(ipBytes))
			if ip != "" {
				return ip
			}
		}
	}

	return "localhost"
}

func runStatus() {
	printHeader("CloudGraph Status Dashboard")

	context := getKubectlCurrentContextFunc()
	namespace := "cloudgraph-system"

	fmt.Printf("Kubernetes Context: %s\n", context)
	fmt.Printf("Namespace: %s\n", namespace)
	fmt.Println("")

	printHeader("System Components Checklist")
	statuses := getDeploymentStatusesFunc(namespace)
	if len(statuses) == 0 {
		printWarning("No deployments found in namespace 'cloudgraph-system' or cluster unreachable")
	} else {
		for name, status := range statuses {
			fmt.Printf("%s: %s\n", name, status)
		}
	}

	fmt.Println("")
	printHeader("Access Information")
	publicIP := getPublicIP()
	hosts := getIngressHostsFunc(namespace)
	if len(hosts) > 0 {
		for _, host := range hosts {
			if host == "localhost" || host == "cloudgraph.local" {
				fmt.Printf("CloudGraph UI: http://%s/ (or http://%s/ with hosts file mapped)\n", publicIP, host)
			} else {
				fmt.Printf("CloudGraph UI: http://%s/\n", host)
			}
		}
	} else {
		fmt.Printf("CloudGraph UI: http://%s/\n", publicIP)
	}
	qdrantCollections := qdrantCollectionSummaryFunc(namespace)
	if len(qdrantCollections) > 0 {
		fmt.Println("")
		printHeader("Vector Store")
		for _, collection := range qdrantCollections {
			status := collection.Status
			if status == "" {
				status = "unknown"
			}
			if collection.Points > 0 {
				fmt.Printf("Qdrant collection %s: %s (%d points)\n", collection.Name, status, collection.Points)
			} else {
				fmt.Printf("Qdrant collection %s: %s\n", collection.Name, status)
			}
		}
	} else {
		fmt.Println("")
		printWarning("Qdrant not reachable or collections are not yet available")
	}
	fmt.Printf("CloudGraph API: http://%s/api/\n", publicIP)
	fmt.Printf("Neo4j Browser: http://%s:7474/\n", publicIP)
	u, p := getNeo4jAuth(namespace)
	fmt.Printf("  └─ Username: %s\n", u)
	fmt.Printf("  └─ Password: %s\n", p)
	fmt.Printf("Qdrant Dashboard: http://%s:6333/dashboard\n", publicIP)
}

func runDeploy() {
	if runtime.GOOS != "linux" {
		printError("CloudGraph deployment is only supported on Linux.")
		os.Exit(1)
	}

	// Check if a Kubernetes cluster is already active
	hasCluster := false
	if commandExistsFunc("kubectl") {
		cmd := exec.Command("kubectl", "cluster-info")
		if err := cmd.Run(); err == nil {
			hasCluster = true
		}
	}

	if !hasCluster {
		// If no cluster is detected, we require root privileges (sudo) to initialize a local cluster
		isRoot := os.Getuid() == 0 || os.Geteuid() == 0 || os.Getenv("SUDO_UID") != ""
		if !isRoot && os.Getenv("SKIP_ROOT_CHECK") != "true" {
			printError(fmt.Sprintf("No active Kubernetes cluster detected and root privileges (sudo) were not detected. Local cluster initialization requires root privileges. (UID: %d, EUID: %d)", os.Getuid(), os.Geteuid()))
			os.Exit(1)
		}
		ensureKubeconfig()
		_ = checkKubectl()
		if !checkK8sCluster() {
			if !installKubeadm() {
				printError("Failed to initialize Kubernetes cluster.")
				os.Exit(1)
			}
		}
	} else {
		printInfo("Active Kubernetes cluster detected. Skipping root privilege check.")
	}

	// Always ensure kubeconfig is configured for the non-root user (SUDO_USER) if we have the admin.conf file
	ensureKubeconfig()

	ensureLocalStorage()
	ensureIngressController()
	checkHelm()
	createNamespace()
	installCloudGraph()
	waitForDeployment()
	startDatabasePortForwards("cloudgraph-system")

	qdrantCollections := qdrantCollectionSummaryFunc("cloudgraph-system")
	if len(qdrantCollections) > 0 {
		printSuccess("Qdrant collections are available")
	} else {
		printWarning("Qdrant did not report collections yet; check 'cloudgraph status' after the services are up")
	}

	publicIP := getPublicIP()
	printHeader("Setup Completed Successfully!")
	fmt.Println("You can check your pods with:")
	fmt.Println("  kubectl get pods -n cloudgraph-system")
	fmt.Println("")
	fmt.Printf("Access your UI at http://%s/ and API at http://%s/api/\n", publicIP, publicIP)
	fmt.Printf("Neo4j Browser: http://%s:7474/\n", publicIP)
	u, p := getNeo4jAuth("cloudgraph-system")
	fmt.Printf("  └─ Username: %s\n", u)
	fmt.Printf("  └─ Password: %s\n", p)
	fmt.Printf("Qdrant Dashboard: http://%s:6333/dashboard\n", publicIP)
	fmt.Println("")
}

func waitForDeployment() {
	printHeader("Waiting for CloudGraph pods to be ready")
	_ = runCmd("kubectl", "wait", "--for=condition=available", "--timeout=600s",
		"deployment", "-l", "app.kubernetes.io/instance=cloudgraph", "-n", "cloudgraph-system")

	// Wait for Qdrant StatefulSet if it exists in the namespace
	if err := exec.Command("kubectl", "get", "statefulset", "cloudgraph-qdrant", "-n", "cloudgraph-system").Run(); err == nil {
		printInfo("Waiting for Qdrant database to be ready...")
		_ = runCmd("kubectl", "rollout", "status", "statefulset/cloudgraph-qdrant", "-n", "cloudgraph-system", "--timeout=300s")
	}

	// Wait for Neo4j StatefulSet if it exists in the namespace (discover the statefulset name dynamically)
	if out, err := exec.Command("kubectl", "get", "statefulset", "-n", "cloudgraph-system", "-o", "jsonpath={.items[*].metadata.name}").Output(); err == nil {
		names := strings.Fields(string(out))
		for _, name := range names {
			if strings.Contains(name, "neo4j") {
				printInfo(fmt.Sprintf("Waiting for Neo4j database rollout (%s)...", name))
				_ = runCmd("kubectl", "rollout", "status", "statefulset/"+name, "-n", "cloudgraph-system", "--timeout=300s")
			}
		}
	}

	printSuccess("CloudGraph pods are ready")
}

func startDatabasePortForwards(namespace string) {
	printInfo("Configuring database public access tunnels...")

	// Kill any existing port-forward processes first
	_ = exec.Command("pkill", "-f", "kubectl port-forward").Run()

	// Discover Neo4j service
	neo4jSvc := "cloudgraph-neo4j-lb-neo4j"
	if err := exec.Command("kubectl", "get", "svc", neo4jSvc, "-n", namespace).Run(); err != nil {
		neo4jSvc = "cloudgraph"
	}

	// Discover Qdrant service
	qdrantSvc := discoverQdrantService(namespace)
	if qdrantSvc == "" {
		qdrantSvc = "cloudgraph-qdrant"
	}

	// Run background port-forwards using nohup and sh (bind to 0.0.0.0 for public access)
	neo4jCmdStr := fmt.Sprintf("nohup kubectl port-forward -n %s svc/%s 7474:7474 7687:7687 --address 0.0.0.0 >/dev/null 2>&1 &", namespace, neo4jSvc)
	qdrantCmdStr := fmt.Sprintf("nohup kubectl port-forward -n %s svc/%s 6333:6333 --address 0.0.0.0 >/dev/null 2>&1 &", namespace, qdrantSvc)

	_ = exec.Command("sh", "-c", neo4jCmdStr).Run()
	_ = exec.Command("sh", "-c", qdrantCmdStr).Run()

	printSuccess("Tunnels configured: Neo4j (7474) & Qdrant (6333)")
}

func getNeo4jAuth(namespace string) (string, string) {
	if !commandExists("kubectl") {
		return "neo4j", "unknown"
	}
	out, err := exec.Command("kubectl", "get", "secret", "cloudgraph-neo4j-auth",
		"-n", namespace, "-o", "jsonpath={.data.NEO4J_AUTH}").Output()
	if err != nil || len(out) == 0 {
		return "neo4j", "unknown"
	}

	decoded, err := base64.StdEncoding.DecodeString(strings.TrimSpace(string(out)))
	if err != nil {
		return "neo4j", "unknown"
	}

	parts := strings.SplitN(string(decoded), "/", 2)
	if len(parts) == 2 {
		return parts[0], parts[1]
	}
	return "neo4j", string(decoded)
}
