package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

const (
	CloudGraphNamespace = "cloudgraph-system"
)

func uninstallHelmRelease() {
	printHeader("Step 1: Uninstalling CloudGraph Helm Release")

	if commandExists("helm") {
		// Check if release exists
		cmd := exec.Command("helm", "list", "-n", CloudGraphNamespace)
		out, err := cmd.Output()
		if err == nil && strings.Contains(string(out), "cloudgraph") {
			printInfo(fmt.Sprintf("Uninstalling Helm release 'cloudgraph' from namespace '%s'...", CloudGraphNamespace))
			_ = runCmd("helm", "uninstall", "cloudgraph", "-n", CloudGraphNamespace)
			printSuccess("Helm release uninstalled successfully")
		} else {
			printWarning(fmt.Sprintf("No Helm release named 'cloudgraph' found in namespace '%s'", CloudGraphNamespace))
		}
	} else {
		printWarning("Helm is not installed, skipping Helm release uninstallation")
	}
}

func deleteNamespace() {
	printHeader("Step 2: Deleting CloudGraph Namespace")

	if commandExists("kubectl") {
		cmd := exec.Command("kubectl", "get", "namespace", CloudGraphNamespace)
		if err := cmd.Run(); err == nil {
			printInfo(fmt.Sprintf("Deleting namespace '%s' (this deletes all PVs, PVCs, secrets, and pods)...", CloudGraphNamespace))
			_ = runCmd("kubectl", "delete", "namespace", CloudGraphNamespace, "--timeout=300s")
			printSuccess(fmt.Sprintf("Namespace '%s' deleted successfully", CloudGraphNamespace))
		} else {
			printWarning(fmt.Sprintf("Namespace '%s' does not exist", CloudGraphNamespace))
		}
	} else {
		printWarning("kubectl is not installed, skipping namespace deletion")
	}
}

func resetKubeadmCluster() {
	printHeader("Step 3: Optional Kubernetes Cluster Reset")

	if !commandExists("kubeadm") {
		printInfo("kubeadm is not installed, skipping cluster reset options")
		return
	}

	fmt.Println("Would you like to reset and dismantle the local Kubernetes cluster (kubeadm)?")
	fmt.Printf("%sWARNING: This will completely destroy the local cluster and stop all running pods!%s\n", Red, NC)
	fmt.Println("Options:")
	fmt.Println("  1) Reset kubeadm cluster and purge configurations (Keep binaries)")
	fmt.Println("  2) Reset kubeadm cluster + Purge all Kubernetes binaries (kubeadm, kubelet, kubectl, containerd, helm)")
	fmt.Println("  3) Keep Kubernetes cluster (Only uninstall CloudGraph)")

	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("Choose option (1-3): ")
		input, err := reader.ReadString('\n')
		if err != nil {
			return
		}
		choice := strings.TrimSpace(input)
		switch choice {
		case "1":
			printInfo("Resetting kubeadm cluster...")
			_ = runCmd("kubeadm", "reset", "-f")
			homeDir := os.Getenv("HOME")
			if homeDir != "" {
				_ = os.RemoveAll(homeDir + "/.kube")
			}
			_ = os.RemoveAll("/etc/kubernetes/")
			_ = os.RemoveAll("/var/lib/etcd/")
			_ = os.RemoveAll("/var/lib/kubelet/")
			_ = os.RemoveAll("/var/run/kubernetes/")
			_ = os.RemoveAll("/var/lib/dockershim/")

			printInfo("Flushing iptables network rules...")
			_ = exec.Command("iptables", "-F").Run()
			_ = exec.Command("iptables", "-t", "nat", "-F").Run()
			_ = exec.Command("iptables", "-t", "mangle", "-F").Run()
			_ = exec.Command("iptables", "-t", "raw", "-F").Run()
			printSuccess("Kubeadm cluster reset completed")
			return

		case "2":
			printInfo("Resetting kubeadm cluster...")
			_ = runCmd("kubeadm", "reset", "-f")
			homeDir := os.Getenv("HOME")
			if homeDir != "" {
				_ = os.RemoveAll(homeDir + "/.kube")
			}
			_ = os.RemoveAll("/etc/kubernetes/")
			_ = os.RemoveAll("/var/lib/etcd/")
			_ = os.RemoveAll("/var/lib/kubelet/")

			printInfo("Flushing iptables network rules...")
			_ = exec.Command("iptables", "-F").Run()
			_ = exec.Command("iptables", "-t", "nat", "-F").Run()
			_ = exec.Command("iptables", "-t", "mangle", "-F").Run()
			_ = exec.Command("iptables", "-t", "raw", "-F").Run()

			if runtime.GOOS == "linux" {
				printInfo("Purging Kubernetes packages, containerd, and Helm...")
				_ = runCmd("apt-get", "purge", "-y", "kubeadm", "kubelet", "kubectl", "helm", "containerd", "conntrack")
				_ = runCmd("apt-get", "autoremove", "-y")

				printInfo("Cleaning package manager lists and keys...")
				_ = os.Remove("/etc/apt/sources.list.d/kubernetes.list")
				_ = os.Remove("/etc/apt/keyrings/kubernetes-apt-keyring.gpg")
				_ = os.Remove("/etc/apt/sources.list.d/helm-stable-debian.list")
				_ = os.RemoveAll("/etc/containerd/")
			}
			printSuccess("Kubeadm cluster and system binaries purged successfully")
			return

		case "3":
			printInfo("Keeping local Kubernetes cluster intact.")
			return

		default:
			printError("Invalid option")
		}
	}
}

func runUninstall() {
	if runtime.GOOS != "linux" {
		printError("CloudGraph uninstallation is only supported on Linux.")
		os.Exit(1)
	}

	printHeader("CloudGraph Uninstallation")
	fmt.Println("")

	if os.Getenv("SKIP_ROOT_CHECK") != "true" && os.Getuid() != 0 && os.Geteuid() != 0 && commandExists("kubeadm") {
		printWarning("This command may require sudo/root privileges if you choose to reset kubeadm.")
	}

	uninstallHelmRelease()
	deleteNamespace()
	resetKubeadmCluster()

	printHeader("Uninstallation Complete!")
	printSuccess("CloudGraph uninstallation finished.")
	fmt.Println("")
}
