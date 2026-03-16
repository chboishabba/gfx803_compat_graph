from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
import networkx as nx
from graph_schema import add_node, add_edge, NodeSpec, EdgeSpec

# NOTE: In a real environment, we would use requests to hit the GitHub API.
# Here, we will simulate the mining process or use the provided search tools 
# if we needed live data. For now, we will implement the structure and 
# seed it with the "mined" data from the CONTEXT.md and ROCm issue.
import urllib.request
import urllib.parse


REPOS = [
    "robertrosenbusch/gfx803_rocm",
    "robertrosenbusch/gfx803_rocm57_pt23",
    "lamikr/rocm_sdk_builder",
    "chboishabba/gfx803_compat_graph",
    "chboishabba/rr_gfx803_rocm",
]

def extract_versions(text: str) -> Tuple[List[str], List[str]]:
    kernels = re.findall(r"kernel\s?(\d+\.\d+)", text, re.I)
    rocms = re.findall(r"rocm\s?(\d+\.\d+)", text, re.I)
    return list(set(kernels)), list(set(rocms))

def mine_local_content(g: nx.MultiDiGraph, content: str, source_id: str):
    """
    Extracts nodes and edges from a block of text and attaches them to a source node.
    """
    kernels, rocms = extract_versions(content)
    
    for k in kernels:
        node_id = f"kernel:{k}"
        if node_id not in g:
            add_node(g, NodeSpec(
                node_id=node_id,
                label=f"Linux Kernel {k}",
                kind="kernel_version",
                status="context",
                confidence=0.9,
                source="miner"
            ))
        add_edge(g, EdgeSpec(
            src=source_id,
            dst=node_id,
            relation="mentions",
            status="known_known",
            confidence=1.0,
            source="miner"
        ))

    for r in rocms:
        node_id = f"rocm:{r}"
        if node_id not in g:
            # Check if it exists with a slightly different ID or label
            add_node(g, NodeSpec(
                node_id=node_id,
                label=f"ROCm {r}",
                kind="rocm_version",
                status="context",
                confidence=0.9,
                source="miner"
            ))
        add_edge(g, EdgeSpec(
            src=source_id,
            dst=node_id,
            relation="mentions",
            status="known_known",
            confidence=1.0,
            source="miner"
        ))

def run_miner(g: nx.MultiDiGraph):
    # Mine technical identifiers from the local conversation transcript
    transcript_path = Path("ROCm RX580 noise issue.txt")
    if transcript_path.exists():
        content = transcript_path.read_text()
        mine_local_content(g, content, "discussion:rocm_rx580_noise_issue")
        
        # Manually add the host node from the transcript
        if "discussion:rocm_rx580_noise_issue" not in g:
            add_node(g, NodeSpec(
                node_id="discussion:rocm_rx580_noise_issue",
                label="ROCm RX580 noise issue transcript",
                kind="discussion",
                status="known_known",
                confidence=1.0,
                source="local"
            ))

    # Simulate mining Issue #4965 mentioned in CONTEXT.md
    issue_id = "issue:rocm:4965"
    if issue_id not in g:
        add_node(g, NodeSpec(
            node_id=issue_id,
            label="ROCm/ROCm Issue #4965: kernels > 6.13 crash driver",
            kind="issue",
            status="known_known",
            confidence=0.95,
            source="web"
        ))
    
    mine_local_content(g, "kernels > 6.13 crash driver due to scheduler issues on gfx803", issue_id)
    
    # Link it to the instability observation
    if "obs:kfd_reset_instability" in g:
        add_edge(g, EdgeSpec(
            src=issue_id,
            dst="obs:kfd_reset_instability",
            relation="targets",
            status="known_known",
            confidence=0.9,
            source="miner"
        ))

    # Add Vulkan Runtime node as it was specifically confirmed working by user
    add_node(g, NodeSpec(
        node_id="runtime:vulkan",
        label="Vulkan Runtime",
        kind="runtime",
        status="known_known",
        confidence=1.0,
        source="user_report"
    ))
    
    add_edge(g, EdgeSpec(
        src="hw:rx580",
        dst="runtime:vulkan",
        relation="supports",
        status="known_known",
        confidence=1.0,
        source="user_report"
    ))

    # Real GitHub Mining
    mine_github_issues(g)

def mine_github_issues(g: nx.MultiDiGraph):
    queries = [
        "repo:pytorch/pytorch gfx803",
        "repo:pytorch/pytorch Polaris",
        "repo:ROCm/ROCm gfx803",
        "repo:ROCm/ROCm Polaris"
    ]
    
    for query in queries:
        try:
            url = f"https://api.github.com/search/issues?q={urllib.parse.quote(query)}&per_page=15"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 graph_miner'})
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read())
                
                for item in data.get('items', []):
                    # extract repo name cleanly
                    repo_url = item.get('repository_url', '')
                    repo_name = "/".join(repo_url.split('/')[-2:]) if repo_url else "unknown/unknown"
                    
                    issue_id = f"issue:{repo_name}:{item['number']}".replace("/", ":")
                    
                    if issue_id not in g:
                        add_node(g, NodeSpec(
                            node_id=issue_id,
                            label=f"{repo_name} #{item['number']}: {item['title']}",
                            kind="issue",
                            status="context",
                            confidence=0.8,
                            source="github_api",
                            attrs={"url": item['html_url'], "state": item['state']}
                        ))
                    
                    if "gfx803" in query or "Polaris" in query:
                        add_edge(g, EdgeSpec(
                            src=issue_id,
                            dst="hw:rx580",
                            relation="mentions",
                            status="context",
                            confidence=0.8,
                            source="github_api"
                        ))
                        
                    mine_local_content(g, item.get('body', '') or '', issue_id)
        except Exception as e:
            print(f"Error fetching {query} from GitHub API: {e}")

