package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

var linesBaseURL = "https://api.sofiatransport.com/v3/lines/%v"
var linesStopsURL = "https://api.sofiatransport.com/v3/lines/%v/%v"

var conf *configuration

var lineTypes = []int{0, 1, 2}
var wg sync.WaitGroup
var count int64
var descriptionsFileName = "descriptions.txt"

type configuration struct {
	APIKey string `json:"API_KEY"`
	UserID string `json:"USER_ID"`
}

type line struct {
	Type int    `json:"type"`
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type lines []line

type stop struct {
	ID   int    `json:"id"`
	Code int    `json:"code"`
	Name string `json:"name"`
}

type route struct {
	ID    int    `json:"id"`
	Stops []stop `json:"stops"`
}

type routes []route

type lineInfo struct {
	Line   line   `json:"line"`
	Routes routes `json:"routes"`
}

var netClient = &http.Client{
	Timeout: time.Minute * 2,
	Transport: &http.Transport{
		TLSHandshakeTimeout: 0 * time.Second,
	},
}

func getAllLines(c chan string) {
	for _, value := range lineTypes {
		request := generateRequest(fmt.Sprintf(linesBaseURL, value))
		res, err := netClient.Do(request)
		if err != nil {
			return
		}
		defer res.Body.Close()
		data, _ := ioutil.ReadAll(res.Body)
		var ln lines
		json.Unmarshal(data, &ln)
		for _, v := range ln {
			go readLineStops(v, c)
		}
	}
}

func readLineStops(l line, c chan string) {
	wg.Add(1)
	request := generateRequest(fmt.Sprintf(linesStopsURL, l.Type, l.ID))
	res, err := netClient.Do(request)
	if err != nil {
		wg.Done()
		return
	}
	defer res.Body.Close()
	data, _ := ioutil.ReadAll(res.Body)
	li := new(lineInfo)
	json.Unmarshal(data, li)
	for _, route := range li.Routes {
		direction := fmt.Sprintf("%v-%v", route.Stops[0].Name, route.Stops[len(route.Stops)-1].Name)
		for _, stop := range route.Stops {
			id := fmt.Sprintf("%v,%v,%v", l.Type, l.Name, stop.Code)
			c <- id + "=" + direction
			atomic.AddInt64(&count, 1)
		}
	}
	wg.Done()
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func writeToFile(c chan string) {
	f, err := os.Create(descriptionsFileName)
	check(err)
	w := bufio.NewWriter(f)
	for i := 0; i < int(count); i++ {
		if i != int(count)-1 {
			w.WriteString(<-c + ";")
		} else {
			w.WriteString(<-c)
		}
	}
	w.Flush()
}

func writeToFileString(descriptions string) {
	f, err := os.Create(descriptionsFileName)
	check(err)
	w := bufio.NewWriter(f)
	w.WriteString(descriptions)
	w.Flush()
}

func getStringFromChannel(c chan string) string {
	var buffer bytes.Buffer
	sorted := make([]string, int(count))
	for i := 0; i < int(count); i++ {
		sorted[i] = <-c
	}
	sort.Strings(sorted)
	for i := 0; i < int(count); i++ {
		if i != int(count)-1 {
			buffer.WriteString(sorted[i] + ";")
		} else {
			buffer.WriteString(sorted[i])
		}
	}
	return buffer.String()
}

func generateRequest(url string) *http.Request {
	request, _ := http.NewRequest("GET", url, nil)
	request.Header.Set("X-Api-Key", conf.APIKey)
	request.Header.Set("X-User-Id", conf.UserID)
	return request
}

func compare(newDesc string) bool {
	if _, err := os.Stat(descriptionsFileName); err != nil {
		return true
	}
	oldDesc, _ := ioutil.ReadFile(descriptionsFileName)
	return string(oldDesc) == newDesc
}

func main() {
	data, _ := ioutil.ReadFile("config.json")
	conf = new(configuration)
	json.Unmarshal(data, conf)

	c := make(chan string, 10000)
	start := time.Now()

	getAllLines(c)

	wg.Wait()
	st := getStringFromChannel(c)
	if compare(st) {
		writeToFileString(st)
		UploadDescriptionsToGithub(descriptionsFileName)
	}

	fmt.Println(count)
	fmt.Println(time.Since(start))
}
