package main

import (
	"bufio"
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
	if commandExists("kubectl") {
		printSuccess("kubectl found")
		return true
	}
	printError("kubectl not found")
	return false
}

func checkK8sCluster() bool {
	printHeader("Checking for Kubernetes cluster")
	if !commandExists("kubectl") {
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
	goos := runtime.GOOS
	if goos == "darwin" {
		printInfo("macOS detected - using Docker Desktop Kubernetes")
		fmt.Println("Please enable Kubernetes in Docker Desktop settings")
		os.Exit(1)
	} else if goos == "linux" {
		printInfo("Linux detected - installing kubeadm cluster")
		return installKubeadmLinux()
	} else {
		printError(fmt.Sprintf("Unsupported OS: %s", goos))
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
	} else if runtime.GOOS == "darwin" {
		out, err := commandOutput("sysctl", "-n", "hw.memsize")
		if err == nil {
			bytes, err := strconv.ParseFloat(strings.TrimSpace(out), 64)
			if err == nil {
				return bytes / 1024.0 / 1024.0 / 1024.0
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
	checkInternetConnection()

	if commandExists("kubectl") {
		printSuccess("kubectl found")
	} else {
		printError("kubectl not found")
	}

	if commandExists("kubectl") && exec.Command("kubectl", "cluster-info").Run() == nil {
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

	fmt.Println("")
	printInfo("Run: sudo cloudgraph deploy")
}

func runStatus() {
	printHeader("CloudGraph Status Dashboard")

	context := getKubectlCurrentContext()
	namespace := "cloudgraph-system"

	fmt.Printf("Kubernetes Context: %s\n", context)
	fmt.Printf("Namespace: %s\n", namespace)
	fmt.Println("")

	printHeader("System Components Checklist")
	statuses := getDeploymentStatuses(namespace)
	if len(statuses) == 0 {
		printWarning("No deployments found in namespace 'cloudgraph-system' or cluster unreachable")
	} else {
		for name, status := range statuses {
			fmt.Printf("%s: %s\n", name, status)
		}
	}

	fmt.Println("")
	printHeader("Access Information")
	hosts := getIngressHosts(namespace)
	if len(hosts) > 0 {
		for _, host := range hosts {
			fmt.Printf("CloudGraph UI: http://%s/\n", host)
		}
	} else {
		fmt.Println("CloudGraph UI: http://localhost/")
	}
	fmt.Println("CloudGraph API: http://localhost:8080/")
}

func runDeploy() {
	if runtime.GOOS != "linux" {
		printError("CloudGraph deployment is only supported on Linux.")
		os.Exit(1)
	}

	// Check if a Kubernetes cluster is already active
	hasCluster := false
	if commandExists("kubectl") {
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

	ensureLocalStorage()
	ensureIngressController()
	checkHelm()
	createNamespace()
	installCloudGraph()
	waitForDeployment()

	printHeader("Setup Completed Successfully!")
	fmt.Println("You can check your pods with:")
	fmt.Println("  kubectl get pods -n cloudgraph-system")
	fmt.Println("")
	fmt.Println("Access your UI at http://localhost/ and API at http://localhost/api/")
	fmt.Println("")
}

func waitForDeployment() {
	printHeader("Waiting for CloudGraph pods to be ready")
	_ = runCmd("kubectl", "wait", "--for=condition=available", "--timeout=600s",
		"deployment", "-l", "app.kubernetes.io/instance=cloudgraph", "-n", "cloudgraph-system")
	printSuccess("CloudGraph pods are ready")
}
