"""ScrnaClaw Skill Registry.

Centralises skill definition, discovery, and loading across all omics domains.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import scrna_claw
from scrna_claw.core.lazy_metadata import LazySkillMetadata

logger = logging.getLogger(__name__)

# Base directories
SCRNA_CLAW_DIR = Path(scrna_claw.__file__).resolve().parent.parent
SKILLS_DIR = SCRNA_CLAW_DIR / "skills"


class OmicsRegistry:
    """Manages skill definitions and dynamic discovery."""

    def __init__(self):
        self.skills: dict[str, dict[str, Any]] = {}
        self.domains = {
            domain: dict(info)
            for domain, info in _HARDCODED_DOMAINS.items()
        }
        self._loaded = False
        self.lazy_skills: dict[str, LazySkillMetadata] = {}

    @staticmethod
    def _top_level_python_files(skill_path: Path) -> list[Path]:
        """Return runnable top-level Python files in a skill directory."""
        return sorted(
            path for path in skill_path.glob("*.py")
            if path.name != "__init__.py" and not path.name.startswith("test_")
        )

    @classmethod
    def _looks_like_skill_dir(cls, skill_path: Path) -> bool:
        """Heuristically decide whether a directory is a skill directory."""
        if (skill_path / "SKILL.md").exists():
            return True

        expected = skill_path / f"{skill_path.name.replace('-', '_')}.py"
        if expected.exists():
            return True

        return len(cls._top_level_python_files(skill_path)) == 1

    @classmethod
    def _is_enabled_skill_dir(cls, skill_path: Path) -> bool:
        try:
            from scrna_claw.extensions import load_extension_state

            return load_extension_state(skill_path).enabled
        except Exception:
            return True

    @classmethod
    def _iter_skill_dirs(cls, domain_path: Path):
        """Yield skill directories, handling optional subdomain nesting.

        Supports both flat layouts (spatial/spatial-preprocess/) and nested
        layouts with a subdomain tier (singlecell/scrna/sc-qc/).  A child
        directory is treated as a skill if it contains a matching
        ``<dir_name>.py`` script or a ``SKILL.md``.  Otherwise it is assumed
        to be a subdomain container and scanned one level deeper.
        """
        for child in domain_path.iterdir():
            if not child.is_dir() or child.name.startswith(('.', '__', '_')):
                continue
            if domain_path.name != "orchestrator" and child.name == "orchestrator":
                continue
            if not cls._is_enabled_skill_dir(child):
                continue

            if cls._looks_like_skill_dir(child):
                yield child
            else:
                # Subdomain container (e.g., scrna/, scatac/, multiome/)
                for grandchild in child.iterdir():
                    if not grandchild.is_dir() or grandchild.name.startswith(('.', '__', '_')):
                        continue
                    if domain_path.name != "orchestrator" and grandchild.name == "orchestrator":
                        continue
                    if not cls._is_enabled_skill_dir(grandchild):
                        continue
                    if cls._looks_like_skill_dir(grandchild):
                        yield grandchild

    @classmethod
    def _resolve_script_path(
        cls,
        skill_path: Path,
        lazy: LazySkillMetadata | None = None,
    ) -> Path | None:
        """Resolve the runnable script for a skill directory."""
        candidates: list[Path] = []

        if lazy and lazy.script:
            candidates.append(skill_path / lazy.script)

        expected = skill_path / f"{skill_path.name.replace('-', '_')}.py"
        candidates.append(expected)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        py_files = cls._top_level_python_files(skill_path)
        if len(py_files) == 1:
            return py_files[0]

        return None

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _register_skill_entry(
        self,
        canonical_alias: str,
        info: dict[str, Any],
        *,
        skill_dir_name: str,
    ) -> None:
        """Register a primary skill entry plus all supported lookup aliases."""
        self.skills[canonical_alias] = info

        lookup_keys: list[str] = list(info.get("legacy_aliases", []))
        if skill_dir_name == canonical_alias or skill_dir_name not in _HARDCODED_SKILLS:
            lookup_keys.append(skill_dir_name)

        for key in self._unique_strings(lookup_keys):
            if key == canonical_alias:
                continue
            if key not in self.skills:
                self.skills[key] = info

    def load_all(self, skills_dir: Path | None = None) -> None:
        """Dynamically load and merge skills from the filesystem.

        For each skill directory found, metadata is read from SKILL.md first.
        The hardcoded ``_HARDCODED_SKILLS`` dict fills in any fields that
        SKILL.md does not define (backward-compatible fallback).
        """
        if self._loaded:
            return

        target_dir = skills_dir or SKILLS_DIR
        if not target_dir.exists():
            return

        # Ensure lightweight metadata is available
        if not self.lazy_skills:
            self.load_lightweight(target_dir)

        # Scan domain directories
        for domain_path in target_dir.iterdir():
            if not domain_path.is_dir() or domain_path.name.startswith(('.', '__')):
                continue

            domain_name = domain_path.name

            # Scan skill directories (handles subdomain nesting)
            for skill_path in self._iter_skill_dirs(domain_path):
                skill_dir_name = skill_path.name
                lazy = self.lazy_skills.get(skill_dir_name)

                script_path_candidate = self._resolve_script_path(skill_path, lazy=lazy)
                if script_path_candidate is None:
                    continue

                # Determine the registry alias for this skill.
                # Check if a hardcoded entry already maps to this script.
                hardcoded_alias = None
                hardcoded_info = None
                for alias, info in _HARDCODED_SKILLS.items():
                    if Path(info.get("script")) == script_path_candidate:
                        hardcoded_alias = alias
                        hardcoded_info = info
                        break

                canonical_alias = (
                    (lazy.name if lazy and lazy.name else "")
                    or hardcoded_alias
                    or skill_dir_name
                )

                # Build skill_info from SKILL.md metadata (primary source)
                if lazy and lazy.description:
                    legacy_aliases = list(lazy.legacy_aliases or [])
                    if hardcoded_alias and hardcoded_alias != canonical_alias:
                        legacy_aliases.append(hardcoded_alias)
                    md_info: dict[str, Any] = {
                        "domain": lazy.domain or domain_name,
                        "alias": canonical_alias,
                        "canonical_name": canonical_alias,
                        "directory_name": skill_dir_name,
                        "script": script_path_candidate,
                        "demo_args": ["--demo"],
                        "description": lazy.description,
                        "trigger_keywords": lazy.trigger_keywords or [],
                        "allowed_extra_flags": lazy.allowed_extra_flags or set(),
                        "legacy_aliases": self._unique_strings(legacy_aliases),
                        "saves_h5ad": lazy.saves_h5ad,
                        "requires_preprocessed": lazy.requires_preprocessed,
                        "param_hints": lazy.param_hints,
                    }
                else:
                    # No SKILL.md or empty — minimal dynamic entry
                    md_info = {
                        "domain": domain_name,
                        "alias": canonical_alias,
                        "canonical_name": canonical_alias,
                        "directory_name": skill_dir_name,
                        "script": script_path_candidate,
                        "demo_args": ["--demo"],
                        "description": f"Dynamically loaded {canonical_alias} skill",
                        "trigger_keywords": [],
                        "allowed_extra_flags": set(),
                        "legacy_aliases": self._unique_strings(
                            [hardcoded_alias] if hardcoded_alias and hardcoded_alias != canonical_alias else []
                        ),
                        "saves_h5ad": False,
                    }

                # Merge: hardcoded fills gaps that SKILL.md didn't provide
                if hardcoded_info:
                    for key, value in hardcoded_info.items():
                        if key == "alias":
                            continue
                        if key == "legacy_aliases":
                            merged_aliases = list(md_info.get("legacy_aliases", []))
                            merged_aliases.extend(value or [])
                            if hardcoded_alias and hardcoded_alias != canonical_alias:
                                merged_aliases.append(hardcoded_alias)
                            md_info["legacy_aliases"] = self._unique_strings(merged_aliases)
                            continue
                        if key not in md_info:
                            md_info[key] = value
                        elif key == "allowed_extra_flags" and not md_info[key]:
                            # If SKILL.md has empty flags, use hardcoded
                            md_info[key] = value
                        elif key == "description" and md_info[key].startswith("Dynamically loaded"):
                            md_info[key] = value
                else:
                    md_info["legacy_aliases"] = self._unique_strings(md_info.get("legacy_aliases", []))

                self._register_skill_entry(
                    canonical_alias,
                    md_info,
                    skill_dir_name=skill_dir_name,
                )


        # Fallback: register any hardcoded skills not discovered on filesystem
        for alias, info in _HARDCODED_SKILLS.items():
            if alias not in self.skills:
                self.skills[alias] = info
                # Also register legacy aliases from hardcoded
                for la in info.get("legacy_aliases", []):
                    if la not in self.skills:
                        self.skills[la] = info

        self._refresh_domain_skill_counts()
        self._loaded = True

    def load_lightweight(self, skills_dir: Path | None = None) -> None:
        """Load only basic skill metadata for fast startup."""
        target_dir = skills_dir or SKILLS_DIR
        if not target_dir.exists():
            return

        for domain_path in target_dir.iterdir():
            if not domain_path.is_dir() or domain_path.name.startswith(('.', '__')):
                continue

            for skill_path in self._iter_skill_dirs(domain_path):
                skill_md = skill_path / "SKILL.md"
                if not skill_md.exists():
                    continue

                lazy = LazySkillMetadata(skill_path)
                skill_key = skill_path.name
                self.lazy_skills[skill_key] = lazy

    def _resolve_alias(self, skill_dir_name: str) -> str:
        """Map a skill directory name to its registry alias.

        Returns the canonical skill name when the directory or a legacy alias is known.
        """
        if not self._loaded:
            self.load_all()

        info = self.skills.get(skill_dir_name)
        if info:
            return str(info.get("alias", skill_dir_name))

        for info in _HARDCODED_SKILLS.values():
            script_path = info.get("script")
            if script_path and Path(script_path).parent.name == skill_dir_name:
                return str(info.get("alias", skill_dir_name))
        return skill_dir_name

    def iter_primary_skills(
        self,
        domain: str | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return the canonical skill entries, excluding alias pointers."""
        if not self._loaded:
            self.load_all()

        items: list[tuple[str, dict[str, Any]]] = []
        for alias, info in self.skills.items():
            if alias != info.get("alias", alias):
                continue
            if domain and info.get("domain") != domain:
                continue
            items.append((alias, info))
        return items

    def build_skill_catalog(self, domain: str | None = None) -> dict[str, str]:
        """Return a canonical skill->description catalog for a domain."""
        return {
            alias: info.get("description", "")
            for alias, info in self.iter_primary_skills(domain=domain)
        }

    def build_keyword_map(
        self,
        domain: str | None = None,
        fallback_map: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build keyword->skill_alias map from SKILL.md trigger_keywords.

        Args:
            domain: If provided, only include skills from this domain.
            fallback_map: Legacy hardcoded map merged underneath
                          (SKILL.md keywords take priority).

        Returns:
            Dict mapping lowercase keyword to skill alias.
        """
        if not self.lazy_skills:
            self.load_lightweight()

        keyword_map: dict[str, str] = {}

        # Start with fallback so SKILL.md keywords override
        if fallback_map:
            keyword_map.update(fallback_map)

        for skill_key, lazy in self.lazy_skills.items():
            if domain and lazy.domain != domain:
                continue

            skill_alias = lazy.name or self._resolve_alias(skill_key)

            for kw in lazy.trigger_keywords:
                keyword_map[kw.lower()] = skill_alias

        return keyword_map

    def _refresh_domain_skill_counts(self) -> None:
        """Update domain skill counts from loaded canonical entries."""
        counts: dict[str, int] = {
            domain: 0
            for domain in self.domains
        }
        for alias, info in self.skills.items():
            if alias != info.get("alias", alias):
                continue
            domain = str(info.get("domain", "")).strip()
            if not domain:
                continue
            counts[domain] = counts.get(domain, 0) + 1

        for domain, count in counts.items():
            if domain not in self.domains:
                self.domains[domain] = {"name": domain, "primary_data_types": []}
            self.domains[domain]["skill_count"] = count


def ensure_registry_loaded(skills_dir: Path | None = None) -> OmicsRegistry:
    """Return the shared registry after ensuring full skill metadata is loaded."""
    registry.load_all(skills_dir)
    return registry


# ---------------------------------------------------------------------------
# Baseline hardcoded definitions for stable legacy mapping
# ---------------------------------------------------------------------------

_HARDCODED_DOMAINS = {
    "spatial": {
        "name": "Spatial Transcriptomics",
        "primary_data_types": ["h5ad", "h5", "zarr", "loom"],
        "skill_count": 17,
    },
    "singlecell": {
        "name": "Single-Cell Omics",
        "primary_data_types": ["h5ad", "h5", "loom", "mtx"],
        "skill_count": 14,
    },
}


_HARDCODED_SKILLS: dict[str, dict[str, Any]] = {
    "spatial-preprocessing": {
        "domain": "spatial",
        "alias": "spatial-preprocessing",
        "legacy_aliases": ["preprocess"],
        "script": SKILLS_DIR / "spatial" / "spatial-preprocess" / "spatial_preprocess.py",
        "demo_args": ["--demo"],
        "description": "Spatial data QC, normalization, HVG, PCA/UMAP, Leiden clustering",
        "allowed_extra_flags": {
            "--data-type", "--min-genes", "--min-cells", "--max-mt-pct",
            "--max-genes", "--n-top-hvg", "--n-pcs", "--n-neighbors",
            "--leiden-resolution", "--resolutions", "--species", "--tissue",
        },
        "saves_h5ad": True,
    },
    "spatial-domain-identification": {
        "domain": "spatial",
        "alias": "spatial-domain-identification",
        "legacy_aliases": ["domains"],
        "script": SKILLS_DIR / "spatial" / "spatial-domains" / "spatial_domains.py",
        "demo_args": ["--demo"],
        "description": "Tissue region/niche identification (Leiden, Louvain, SpaGCN, STAGATE, GraphST, BANKSY)",
        "allowed_extra_flags": {
            "--method", "--n-domains", "--resolution",
            "--spatial-weight", "--rad-cutoff", "--lambda-param", "--refine",
        },
        "saves_h5ad": True,
    },
    "spatial-cell-annotation": {
        "domain": "spatial",
        "alias": "spatial-cell-annotation",
        "legacy_aliases": ["annotate"],
        "script": SKILLS_DIR / "spatial" / "spatial-annotate" / "spatial_annotate.py",
        "demo_args": ["--demo"],
        "description": "Cell type annotation (Scanpy marker overlap, Tangram, scANVI, CellAssign)",
        "allowed_extra_flags": {
            "--batch-key",
            "--cell-type-key",
            "--cellassign-max-epochs",
            "--cluster-key",
            "--layer",
            "--marker-n-genes",
            "--marker-overlap-method",
            "--marker-overlap-normalize",
            "--marker-padj-cutoff",
            "--marker-rank-method",
            "--method",
            "--model",
            "--reference",
            "--scanvi-max-epochs",
            "--scanvi-n-hidden",
            "--scanvi-n-layers",
            "--scanvi-n-latent",
            "--species",
            "--tangram-device",
            "--tangram-num-epochs",
            "--tangram-train-genes",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-deconvolution": {
        "domain": "spatial",
        "alias": "spatial-deconvolution",
        "legacy_aliases": ["deconv"],
        "script": SKILLS_DIR / "spatial" / "spatial-deconv" / "spatial_deconv.py",
        "demo_args": ["--demo"],
        "description": "Spatial deconvolution — Cell2location, RCTD, DestVI, Stereoscope, Tangram, SPOTlight, CARD, FlashDeconv",
        "allowed_extra_flags": {
            "--card-imputation",
            "--card-ineibor",
            "--card-min-count-gene",
            "--card-min-count-spot",
            "--card-num-grids",
            "--card-sample-key",
            "--cell-type-key",
            "--cell2location-detection-alpha",
            "--cell2location-n-cells-per-spot",
            "--cell2location-n-epochs",
            "--destvi-condscvi-epochs",
            "--destvi-dropout-rate",
            "--destvi-n-epochs",
            "--destvi-n-hidden",
            "--destvi-n-latent",
            "--destvi-n-layers",
            "--destvi-vamp-prior-p",
            "--flashdeconv-lambda-spatial",
            "--flashdeconv-n-hvg",
            "--flashdeconv-n-markers-per-type",
            "--flashdeconv-sketch-dim",
            "--method",
            "--no-gpu",
            "--no-spotlight-scale",
            "--rctd-mode",
            "--reference",
            "--spotlight-min-prop",
            "--spotlight-model",
            "--spotlight-n-top",
            "--spotlight-scale",
            "--spotlight-weight-id",
            "--stereoscope-batch-size",
            "--stereoscope-learning-rate",
            "--stereoscope-rna-epochs",
            "--stereoscope-spatial-epochs",
            "--tangram-learning-rate",
            "--tangram-mode",
            "--tangram-n-epochs",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-statistics": {
        "domain": "spatial",
        "alias": "spatial-statistics",
        "legacy_aliases": ["statistics"],
        "script": SKILLS_DIR / "spatial" / "spatial-statistics" / "spatial_statistics.py",
        "demo_args": ["--demo"],
        "description": "Spatial statistics (neighborhood enrichment, Ripley, co-occurrence, Moran/Geary, local hotspots, bivariate Moran, graph centrality)",
        "allowed_extra_flags": {
            "--analysis-type",
            "--centrality-score",
            "--cluster-key",
            "--coocc-interval",
            "--coocc-n-splits",
            "--genes",
            "--getis-star",
            "--local-moran-geoda-quads",
            "--n-top-genes",
            "--no-getis-star",
            "--no-local-moran-geoda-quads",
            "--no-stats-two-tailed",
            "--ripley-max-dist",
            "--ripley-metric",
            "--ripley-mode",
            "--ripley-n-neigh",
            "--ripley-n-observations",
            "--ripley-n-simulations",
            "--ripley-n-steps",
            "--stats-corr-method",
            "--stats-n-neighs",
            "--stats-n-perms",
            "--stats-n-rings",
            "--stats-seed",
            "--stats-two-tailed",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-svg-detection": {
        "domain": "spatial",
        "alias": "spatial-svg-detection",
        "legacy_aliases": ["genes", "spatial-genes"],
        "script": SKILLS_DIR / "spatial" / "spatial-genes" / "spatial_genes.py",
        "demo_args": ["--demo"],
        "description": "Spatially variable genes (Moran's I, SpatialDE, SPARK-X, FlashS)",
        "allowed_extra_flags": {
            "--method",
            "--n-top-genes",
            "--fdr-threshold",
            "--morans-coord-type",
            "--morans-corr-method",
            "--morans-n-neighs",
            "--morans-n-perms",
            "--spatialde-min-counts",
            "--spatialde-no-aeh",
            "--spatialde-aeh-patterns",
            "--spatialde-aeh-lengthscale",
            "--sparkx-num-cores",
            "--sparkx-option",
            "--sparkx-max-genes",
            "--flashs-n-rand-features",
            "--flashs-bandwidth",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-de": {
        "domain": "spatial",
        "alias": "spatial-de",
        "legacy_aliases": ["de"],
        "script": SKILLS_DIR / "spatial" / "spatial-de" / "spatial_de.py",
        "demo_args": ["--demo"],
        "description": "Spatial DE and marker discovery (Scanpy or sample-aware pseudobulk PyDESeq2)",
        "allowed_extra_flags": {
            "--fdr-threshold", "--filter-compare-abs", "--filter-markers", "--group1",
            "--group2", "--groupby", "--log2fc-threshold", "--max-out-group-fraction",
            "--method", "--min-cells-per-sample", "--min-counts-per-gene",
            "--min-fold-change", "--min-in-group-fraction", "--n-top-genes",
            "--no-filter-compare-abs", "--no-filter-markers",
            "--no-pydeseq2-cooks-filter", "--no-pydeseq2-independent-filter",
            "--no-pydeseq2-refit-cooks", "--no-scanpy-pts", "--no-scanpy-rankby-abs",
            "--no-scanpy-tie-correct", "--pydeseq2-alpha", "--pydeseq2-cooks-filter",
            "--pydeseq2-fit-type", "--pydeseq2-independent-filter", "--pydeseq2-n-cpus",
            "--pydeseq2-refit-cooks", "--pydeseq2-size-factors-fit-type", "--sample-key",
            "--scanpy-corr-method", "--scanpy-pts", "--scanpy-rankby-abs",
            "--scanpy-tie-correct",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-condition-comparison": {
        "domain": "spatial",
        "alias": "spatial-condition-comparison",
        "legacy_aliases": ["condition", "spatial-condition"],
        "script": SKILLS_DIR / "spatial" / "spatial-condition" / "spatial_condition.py",
        "demo_args": ["--demo"],
        "description": "Condition comparison with pseudobulk DESeq2 statistics",
        "allowed_extra_flags": {
            "--cluster-key", "--condition-key", "--fdr-threshold", "--log2fc-threshold",
            "--method", "--min-counts-per-gene", "--min-samples-per-condition",
            "--no-pydeseq2-cooks-filter", "--no-pydeseq2-independent-filter",
            "--no-pydeseq2-refit-cooks", "--pydeseq2-alpha", "--pydeseq2-cooks-filter",
            "--pydeseq2-fit-type", "--pydeseq2-independent-filter", "--pydeseq2-n-cpus",
            "--pydeseq2-refit-cooks", "--pydeseq2-size-factors-fit-type",
            "--reference-condition", "--sample-key", "--wilcoxon-alternative",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-cell-communication": {
        "domain": "spatial",
        "alias": "spatial-cell-communication",
        "legacy_aliases": ["communication"],
        "script": SKILLS_DIR / "spatial" / "spatial-communication" / "spatial_communication.py",
        "demo_args": ["--demo"],
        "description": "Cell-cell communication (LIANA+, CellPhoneDB, FastCCC)",
        "allowed_extra_flags": {
            "--method", "--species", "--cell-type-key",
            "--liana-expr-prop", "--liana-min-cells", "--liana-n-perms", "--liana-resource",
            "--cellphonedb-iterations", "--cellphonedb-threshold",
            "--fastccc-single-unit-summary", "--fastccc-complex-aggregation",
            "--fastccc-lr-combination", "--fastccc-min-percentile",
            "--cellchat-prob-type", "--cellchat-min-cells",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-velocity": {
        "domain": "spatial",
        "alias": "spatial-velocity",
        "legacy_aliases": ["velocity"],
        "script": SKILLS_DIR / "spatial" / "spatial-velocity" / "spatial_velocity.py",
        "demo_args": ["--demo"],
        "description": "RNA velocity and cellular dynamics (scVelo, VeloVI)",
        "allowed_extra_flags": {
            "--cluster-key",
            "--dynamical-fit-scaling",
            "--dynamical-fit-steady-states",
            "--dynamical-fit-time",
            "--dynamical-max-iter",
            "--dynamical-n-jobs",
            "--dynamical-n-top-genes",
            "--method",
            "--no-dynamical-fit-scaling",
            "--no-dynamical-fit-steady-states",
            "--no-dynamical-fit-time",
            "--no-velocity-fit-offset",
            "--no-velocity-fit-offset2",
            "--no-velocity-graph-approx",
            "--no-velocity-graph-sqrt-transform",
            "--no-velocity-use-highly-variable",
            "--no-velovi-early-stopping",
            "--velocity-fit-offset",
            "--velocity-fit-offset2",
            "--velocity-graph-approx",
            "--velocity-graph-n-neighbors",
            "--velocity-graph-sqrt-transform",
            "--velocity-min-likelihood",
            "--velocity-min-r2",
            "--velocity-min-shared-counts",
            "--velocity-n-neighbors",
            "--velocity-n-pcs",
            "--velocity-n-top-genes",
            "--velocity-use-highly-variable",
            "--velovi-batch-size",
            "--velovi-dropout-rate",
            "--velovi-early-stopping",
            "--velovi-lr",
            "--velovi-max-epochs",
            "--velovi-n-hidden",
            "--velovi-n-latent",
            "--velovi-n-layers",
            "--velovi-n-samples",
            "--velovi-weight-decay",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-trajectory": {
        "domain": "spatial",
        "alias": "spatial-trajectory",
        "legacy_aliases": ["trajectory"],
        "script": SKILLS_DIR / "spatial" / "spatial-trajectory" / "spatial_trajectory.py",
        "demo_args": ["--demo"],
        "description": "Trajectory inference (CellRank, Palantir, DPT)",
        "allowed_extra_flags": {
            "--method",
            "--cluster-key",
            "--root-cell",
            "--root-cell-type",
            "--dpt-n-dcs",
            "--cellrank-n-states",
            "--cellrank-schur-components",
            "--cellrank-frac-to-keep",
            "--cellrank-use-velocity",
            "--palantir-n-components",
            "--palantir-knn",
            "--palantir-num-waypoints",
            "--palantir-max-iterations",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-enrichment": {
        "domain": "spatial",
        "alias": "spatial-enrichment",
        "legacy_aliases": ["enrichment"],
        "script": SKILLS_DIR / "spatial" / "spatial-enrichment" / "spatial_enrichment.py",
        "demo_args": ["--demo"],
        "description": "Pathway and gene-set enrichment (ORA-style enrichr, prerank GSEA, ssGSEA)",
        "allowed_extra_flags": {
            "--de-corr-method", "--de-method", "--enrichr-log2fc-cutoff",
            "--enrichr-max-genes", "--enrichr-padj-cutoff", "--fdr-threshold",
            "--gene-set", "--gene-set-file", "--groupby", "--gsea-ascending",
            "--gsea-max-size", "--gsea-min-size", "--gsea-permutation-num",
            "--gsea-ranking-metric", "--gsea-seed", "--gsea-threads",
            "--gsea-weight", "--method", "--n-top-terms", "--no-gsea-ascending",
            "--no-ssgsea-ascending", "--source", "--species", "--ssgsea-ascending",
            "--ssgsea-correl-norm-type", "--ssgsea-max-size", "--ssgsea-min-size",
            "--ssgsea-sample-norm-method", "--ssgsea-seed", "--ssgsea-threads",
            "--ssgsea-weight",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-cnv": {
        "domain": "spatial",
        "alias": "spatial-cnv",
        "legacy_aliases": ["cnv"],
        "script": SKILLS_DIR / "spatial" / "spatial-cnv" / "spatial_cnv.py",
        "demo_args": ["--demo"],
        "description": "Copy number variation inference (inferCNVpy, Numbat)",
        "allowed_extra_flags": {
            "--method", "--reference-key", "--reference-cat", "--window-size", "--step",
            "--infercnv-lfc-clip", "--infercnv-dynamic-threshold",
            "--infercnv-exclude-chromosomes", "--infercnv-include-sex-chromosomes",
            "--infercnv-chunksize", "--infercnv-n-jobs",
            "--numbat-genome", "--numbat-max-entropy", "--numbat-min-llr",
            "--numbat-min-cells", "--numbat-ncores",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "spatial-integration": {
        "domain": "spatial",
        "alias": "spatial-integration",
        "legacy_aliases": ["integrate"],
        "script": SKILLS_DIR / "spatial" / "spatial-integrate" / "spatial_integrate.py",
        "demo_args": ["--demo"],
        "description": "Multi-sample integration (Harmony, BBKNN, Scanorama)",
        "allowed_extra_flags": {
            "--method",
            "--batch-key",
            "--harmony-theta",
            "--harmony-lambda",
            "--harmony-max-iter",
            "--bbknn-neighbors-within-batch",
            "--bbknn-n-pcs",
            "--bbknn-trim",
            "--scanorama-knn",
            "--scanorama-sigma",
            "--scanorama-alpha",
            "--scanorama-batch-size",
        },
        "saves_h5ad": True,
    },
    "spatial-registration": {
        "domain": "spatial",
        "alias": "spatial-registration",
        "legacy_aliases": ["register"],
        "script": SKILLS_DIR / "spatial" / "spatial-register" / "spatial_register.py",
        "demo_args": ["--demo"],
        "description": "Spatial registration / slice alignment (PASTE, STalign)",
        "allowed_extra_flags": {
            "--method",
            "--slice-key",
            "--reference-slice",
            "--paste-alpha",
            "--paste-dissimilarity",
            "--paste-use-gpu",
            "--stalign-niter",
            "--stalign-image-size",
            "--stalign-a",
            "--use-expression",
        },
        "saves_h5ad": True,
    },

    # -----------------------------------------------------------------------
    # Single-cell domain
    # -----------------------------------------------------------------------
    "sc-standardize-input": {
        "domain": "singlecell",
        "alias": "sc-standardize-input",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-standardize-input" / "sc_standardize_input.py",
        "demo_args": ["--demo"],
        "description": "Canonicalize single-cell input into a stable AnnData contract for downstream scRNA skills",
        "allowed_extra_flags": {"--species"},
        "saves_h5ad": True,
    },
    "sc-qc": {
        "domain": "singlecell",
        "alias": "sc-qc",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-qc" / "sc_qc.py",
        "demo_args": ["--demo"],
        "description": "Calculate and visualize QC metrics for scRNA-seq data",
        "allowed_extra_flags": {"--species"},
        "saves_h5ad": True,
    },
    "sc-filter": {
        "domain": "singlecell",
        "alias": "sc-filter",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-filter" / "sc_filter.py",
        "demo_args": ["--demo"],
        "description": "Filter cells and genes based on QC metrics with tissue-specific presets",
        "allowed_extra_flags": {
            "--min-genes", "--max-genes", "--min-counts", "--max-counts",
            "--max-mt-percent", "--min-cells", "--tissue",
        },
        "saves_h5ad": True,
    },
    "sc-ambient-removal": {
        "domain": "singlecell",
        "alias": "sc-ambient-removal",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-ambient-removal" / "sc_ambient.py",
        "demo_args": ["--demo"],
        "description": "Remove ambient RNA contamination using CellBender, SoupX, or simple subtraction",
        "allowed_extra_flags": {"--method", "--expected-cells", "--raw-h5", "--raw-matrix-dir", "--filtered-matrix-dir", "--contamination"},
        "saves_h5ad": True,
    },
    "sc-preprocessing": {
        "domain": "singlecell",
        "alias": "sc-preprocessing",
        "legacy_aliases": ["sc-preprocess"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-preprocessing" / "sc_preprocess.py",
        "demo_args": ["--demo"],
        "description": "scRNA-seq base preprocessing: QC-aware filtering, normalization, HVG selection, and PCA",
        "allowed_extra_flags": {
            "--method", "--min-genes", "--min-cells", "--max-mt-pct",
            "--n-top-hvg", "--n-pcs",
            "--normalization-target-sum", "--scanpy-hvg-flavor",
            "--pearson-hvg-flavor", "--pearson-theta",
            "--seurat-normalize-method", "--seurat-scale-factor", "--seurat-hvg-method",
            "--sctransform-regress-mt", "--no-sctransform-regress-mt",
        },
        "saves_h5ad": True,
    },
    "sc-clustering": {
        "domain": "singlecell",
        "alias": "sc-clustering",
        "legacy_aliases": ["sc-dimred-cluster"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-clustering" / "sc_cluster.py",
        "demo_args": ["--demo"],
        "description": "Single-cell neighbors, low-dimensional embedding, and graph clustering from normalized or integrated embeddings",
        "allowed_extra_flags": {
            "--embedding-method", "--cluster-method", "--use-rep", "--n-neighbors", "--n-pcs", "--resolution",
            "--umap-min-dist", "--umap-spread", "--tsne-perplexity", "--tsne-metric", "--diffmap-n-comps",
            "--phate-knn", "--phate-decay",
        },
        "saves_h5ad": True,
        "requires_preprocessed": True,
    },
    "sc-doublet-detection": {
        "domain": "singlecell",
        "alias": "sc-doublet-detection",
        "legacy_aliases": ["sc-doublet"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-doublet-detection" / "sc_doublet.py",
        "demo_args": ["--demo"],
        "description": "Doublet detection annotation (Scrublet, DoubletDetection, scDblFinder, DoubletFinder, scds)",
        "allowed_extra_flags": {
            "--method", "--expected-doublet-rate", "--threshold", "--batch-key",
            "--doubletdetection-n-iters", "--doubletdetection-standard-scaling", "--no-doubletdetection-standard-scaling",
            "--scds-mode",
        },
        "saves_h5ad": True,
    },
    "sc-cell-annotation": {
        "domain": "singlecell",
        "alias": "sc-cell-annotation",
        "legacy_aliases": ["sc-annotate"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-cell-annotation" / "sc_annotate.py",
        "demo_args": ["--demo"],
        "description": "Cell type annotation (markers, CellTypist, PopV-style mapping, KNNPredict-style mapping, SingleR, scmap)",
        "allowed_extra_flags": {"--method", "--reference", "--cluster-key", "--model", "--celltypist-majority-voting", "--no-celltypist-majority-voting"},
        "saves_h5ad": True,
    },
    # sc-trajectory: replaced by sc-pseudotime and sc-velocity
    "sc-pseudotime": {
        "domain": "singlecell",
        "alias": "sc-pseudotime",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-pseudotime" / "sc_pseudotime.py",
        "demo_args": ["--demo"],
        "description": "Pseudotime and fate analysis with DPT, Palantir, VIA, or CellRank",
        "allowed_extra_flags": {
            "--cluster-key", "--root-cluster", "--root-cell", "--n-dcs",
            "--n-genes", "--method", "--palantir-knn", "--palantir-num-waypoints",
            "--palantir-max-iterations", "--palantir-seed", "--via-knn", "--via-seed",
            "--cellrank-n-states", "--cellrank-schur-components", "--cellrank-frac-to-keep",
            "--cellrank-use-velocity",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-velocity": {
        "domain": "singlecell",
        "alias": "sc-velocity",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-velocity" / "sc_velocity.py",
        "demo_args": ["--demo"],
        "description": "RNA velocity analysis with scVelo (requires spliced/unspliced layers)",
        "allowed_extra_flags": {"--method", "--n-jobs"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-batch-integration": {
        "domain": "singlecell",
        "alias": "sc-batch-integration",
        "legacy_aliases": ["sc-integrate"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-batch-integration" / "sc_integrate.py",
        "demo_args": ["--demo"],
        "description": "Multi-sample integration and batch correction (Harmony, scVI, BBKNN, Scanorama, fastMNN, Seurat CCA/RPCA)",
        "allowed_extra_flags": {"--method", "--batch-key", "--n-epochs", "--no-gpu", "--n-latent", "--labels-key", "--harmony-theta", "--bbknn-neighbors-within-batch", "--scanorama-knn", "--integration-features", "--integration-pcs"},
        "saves_h5ad": True,
    },
    "sc-de": {
        "domain": "singlecell",
        "alias": "sc-de",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-de" / "sc_de.py",
        "demo_args": ["--demo"],
        "description": "Differential expression analysis (Wilcoxon, t-test, MAST compatibility, pseudobulk DESeq2 via R)",
        "allowed_extra_flags": {
            "--groupby", "--group1", "--group2", "--method", "--n-top-genes", "--sample-key", "--celltype-key",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-markers": {
        "domain": "singlecell",
        "alias": "sc-markers",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-markers" / "sc_markers.py",
        "demo_args": ["--demo"],
        "description": "Find marker genes for cell clusters using Wilcoxon, t-test, or logistic regression",
        "allowed_extra_flags": {
            "--groupby", "--method", "--n-genes", "--n-top",
            "--min-in-group-fraction", "--min-fold-change", "--max-out-group-fraction",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-grn": {
        "domain": "singlecell",
        "alias": "sc-grn",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-grn" / "sc_grn.py",
        "demo_args": ["--demo"],
        "description": "Gene regulatory network inference with pySCENIC (GRNBoost2, cisTarget, AUCell)",
        "allowed_extra_flags": {
            "--tf-list", "--db", "--motif", "--n-top-targets", "--n-jobs", "--seed",
        },
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-cell-communication": {
        "domain": "singlecell",
        "alias": "sc-cell-communication",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-cell-communication" / "sc_cell_communication.py",
        "demo_args": ["--demo"],
        "description": "Cell-cell communication analysis (builtin, LIANA, CellPhoneDB, CellChat, NicheNet)",
        "allowed_extra_flags": {"--method", "--cell-type-key", "--species", "--cellphonedb-counts-data", "--cellphonedb-iterations", "--cellphonedb-threshold", "--cellphonedb-threads", "--cellphonedb-pvalue", "--condition-key", "--condition-oi", "--condition-ref", "--receiver", "--senders", "--nichenet-top-ligands", "--nichenet-expression-pct"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-differential-abundance": {
        "domain": "singlecell",
        "alias": "sc-differential-abundance",
        "legacy_aliases": ["sc-da", "sc-compositional"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-differential-abundance" / "sc_differential_abundance.py",
        "demo_args": ["--demo"],
        "description": "Differential abundance and compositional analysis (Milo, scCODA)",
        "allowed_extra_flags": {"--method", "--condition-key", "--sample-key", "--cell-type-key", "--contrast", "--reference-cell-type", "--fdr", "--prop", "--n-neighbors", "--min-count"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-metacell": {
        "domain": "singlecell",
        "alias": "sc-metacell",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-metacell" / "sc_metacell.py",
        "demo_args": ["--demo"],
        "description": "Metacell construction and summarization (SEACells-style workflows)",
        "allowed_extra_flags": {"--method", "--use-rep", "--n-metacells", "--celltype-key", "--min-iter", "--max-iter"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-perturb": {
        "domain": "singlecell",
        "alias": "sc-perturb",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-perturb" / "sc_perturb.py",
        "demo_args": ["--demo"],
        "description": "Perturb-seq / CRISPR perturbation analysis with pertpy Mixscape",
        "allowed_extra_flags": {"--method", "--pert-key", "--control", "--split-by", "--n-neighbors", "--logfc-threshold", "--pval-cutoff", "--perturbation-type"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    "sc-perturb-prep": {
        "domain": "singlecell",
        "alias": "sc-perturb-prep",
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-perturb-prep" / "sc_perturb_prep.py",
        "demo_args": ["--demo"],
        "description": "Prepare perturbation-ready AnnData objects from expression data plus sgRNA assignments",
        "allowed_extra_flags": {"--mapping-file", "--barcode-column", "--sgrna-column", "--target-column", "--sep", "--delimiter", "--gene-position", "--pert-key", "--sgrna-key", "--target-key", "--control-patterns", "--control-label", "--keep-multi-guide", "--species"},
        "requires_preprocessed": False,
        "saves_h5ad": True,
    },
    "sc-in-silico-perturbation": {
        "domain": "singlecell",
        "alias": "sc-in-silico-perturbation",
        "legacy_aliases": ["sc-tenifold-knockout"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-in-silico-perturbation" / "sc_in_silico_perturbation.py",
        "demo_args": ["--demo"],
        "description": "In-silico perturbation from WT scRNA-seq, currently with scTenifoldKnk",
        "allowed_extra_flags": {"--ko-gene", "--qc", "--qc-min-lib-size", "--qc-min-cells", "--n-net", "--n-cells", "--n-comp", "--q", "--td-k", "--ma-dim", "--n-cores"},
        "saves_h5ad": False,
    },
    "sc-gene-programs": {
        "domain": "singlecell",
        "alias": "sc-gene-programs",
        "legacy_aliases": ["sc-programs"],
        "script": SKILLS_DIR / "singlecell" / "scrna" / "sc-gene-programs" / "sc_gene_programs.py",
        "demo_args": ["--demo"],
        "description": "Gene program discovery and usage scoring (cNMF / NMF-style workflows)",
        "allowed_extra_flags": {"--method", "--n-programs", "--n-iter", "--seed", "--layer", "--top-genes"},
        "requires_preprocessed": True,
        "saves_h5ad": True,
    },
    # sc-multiome: script not yet implemented

}

# Instantiate the global registry
registry = OmicsRegistry()
