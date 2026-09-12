package main

import (
	"encoding/json"
	"os"
	"slices"
	"testing"
)

type mixedTargetFixture struct {
	Targets []struct {
		Name        string `json:"name"`
		BuildSystem string `json:"build_system"`
	} `json:"targets"`
	DebianTargets   []string `json:"debian_targets"`
	PgrxTargets     []string `json:"pgrx_targets"`
	PgDuckdbTargets []string `json:"pg_duckdb_targets"`
}

func TestEffectiveBuildSystem(t *testing.T) {
	tests := []struct {
		name       string
		metadata   extensionMetadata
		wantSystem string
		wantErr    bool
	}{
		{name: "omitted means Debian", metadata: extensionMetadata{Name: "legacy"}, wantSystem: debianBuildSystem},
		{name: "explicit Debian", metadata: extensionMetadata{Name: "debian", BuildSystem: debianBuildSystem}, wantSystem: debianBuildSystem},
		{name: "pgrx", metadata: extensionMetadata{Name: "pg-jsonschema", BuildSystem: pgrxBuildSystem}, wantSystem: pgrxBuildSystem},
		{name: "pg-duckdb", metadata: extensionMetadata{Name: "pg-duckdb", BuildSystem: pgDuckdbBuildSystem}, wantSystem: pgDuckdbBuildSystem},
		{name: "unknown", metadata: extensionMetadata{Name: "bad", BuildSystem: "unknown"}, wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := effectiveBuildSystem(&tt.metadata)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected an error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.wantSystem {
				t.Fatalf("build system: got %q, want %q", got, tt.wantSystem)
			}
		})
	}
}

func TestMixedTargetRoutingFixture(t *testing.T) {
	data, err := os.ReadFile("testdata/mixed-target-routing.json")
	if err != nil {
		t.Fatalf("read mixed-target fixture: %v", err)
	}

	var fixture mixedTargetFixture
	if err := json.Unmarshal(data, &fixture); err != nil {
		t.Fatalf("decode mixed-target fixture: %v", err)
	}

	debianTargets := make([]string, 0, len(fixture.Targets))
	pgrxTargets := make([]string, 0, len(fixture.Targets))
	pgDuckdbTargets := make([]string, 0, len(fixture.Targets))
	for _, target := range fixture.Targets {
		buildSystem, err := effectiveBuildSystem(&extensionMetadata{
			Name:        target.Name,
			BuildSystem: target.BuildSystem,
		})
		if err != nil {
			t.Fatalf("classify %q: %v", target.Name, err)
		}
		switch buildSystem {
		case debianBuildSystem:
			debianTargets = append(debianTargets, target.Name)
		case pgrxBuildSystem:
			pgrxTargets = append(pgrxTargets, target.Name)
		case pgDuckdbBuildSystem:
			pgDuckdbTargets = append(pgDuckdbTargets, target.Name)
		}
	}

	if !slices.Equal(debianTargets, fixture.DebianTargets) {
		t.Fatalf("Debian targets: got %v, want %v", debianTargets, fixture.DebianTargets)
	}
	if !slices.Equal(pgrxTargets, fixture.PgrxTargets) {
		t.Fatalf("pgrx targets: got %v, want %v", pgrxTargets, fixture.PgrxTargets)
	}
	if !slices.Equal(pgDuckdbTargets, fixture.PgDuckdbTargets) {
		t.Fatalf("pg-duckdb targets: got %v, want %v", pgDuckdbTargets, fixture.PgDuckdbTargets)
	}
}

func TestBuildMatrixFromMetadata(t *testing.T) {
	tests := []struct {
		name     string
		versions versionMap
		want     []buildCombo
	}{
		{
			name: "two distros, one major",
			versions: versionMap{
				"trixie":   {"18": {Package: "x"}},
				"bookworm": {"18": {Package: "x"}},
			},
			want: []buildCombo{
				{Distribution: "bookworm", MajorVersion: "18"},
				{Distribution: "trixie", MajorVersion: "18"},
			},
		},
		{
			name: "single distro",
			versions: versionMap{
				"trixie": {"18": {Package: "x"}},
			},
			want: []buildCombo{
				{Distribution: "trixie", MajorVersion: "18"},
			},
		},
		{
			// Each distribution declares its own set of PG majors:
			// bookworm builds 17 and 18, trixie builds only 18.
			// There must be no trixie/17 combo.
			name: "each distro declares its own majors",
			versions: versionMap{
				"bookworm": {"17": {Package: "x"}, "18": {Package: "x"}},
				"trixie":   {"18": {Package: "x"}},
			},
			want: []buildCombo{
				{Distribution: "bookworm", MajorVersion: "17"},
				{Distribution: "bookworm", MajorVersion: "18"},
				{Distribution: "trixie", MajorVersion: "18"},
			},
		},
		{
			name:     "empty versions",
			versions: versionMap{},
			want:     nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			matrix := buildMatrixFromMetadata(&extensionMetadata{Versions: tt.versions})

			if !slices.Equal(matrix.Combinations, tt.want) {
				t.Errorf("Combinations: got %v, want %v", matrix.Combinations, tt.want)
			}
		})
	}
}

func TestBuildMatrix(t *testing.T) {
	matrix := buildMatrixFromMetadata(&extensionMetadata{Versions: versionMap{
		"bookworm": {"18": {Package: "x"}, "19": {Package: "x"}},
		"trixie":   {"18": {Package: "x"}},
	}})

	t.Run("contains", func(t *testing.T) {
		cases := []struct {
			distro string
			major  string
			want   bool
		}{
			{"bookworm", "18", true},
			{"bookworm", "19", true},
			{"trixie", "18", true},
			{"trixie", "19", false},   // trixie does not declare 19
			{"bullseye", "18", false}, // bullseye is not present
		}
		for _, c := range cases {
			if got := matrix.contains(c.distro, c.major); got != c.want {
				t.Errorf("contains(%q, %q) = %v, want %v", c.distro, c.major, got, c.want)
			}
		}
	})

	t.Run("hasDistribution", func(t *testing.T) {
		if !matrix.hasDistribution("trixie") {
			t.Error("hasDistribution(trixie) = false, want true")
		}
		if matrix.hasDistribution("bullseye") {
			t.Error("hasDistribution(bullseye) = true, want false")
		}
	})
}
