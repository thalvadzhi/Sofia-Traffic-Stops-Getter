package main

import (
	"fmt"
	"os/exec"
)

func add(fileName string) {
	cmd := exec.Command("git", "add", fileName)
	err := cmd.Run()
	fmt.Println(err)
}

func commit() {
	cmd := exec.Command("git", "commit", "-m new version of descriptions")
	err := cmd.Run()
	fmt.Println(err)
}

func push() {
	cmd := exec.Command("git", "push", "origin", "master")
	err := cmd.Run()
	fmt.Println(err)
}

//UploadDescriptionsToGithub adds, commits and pushes to github
func UploadDescriptionsToGithub(fileName string) {
	add(fileName)
	commit()
	push()
}
