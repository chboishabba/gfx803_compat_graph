from graph_miner import mine_github_issues
from graph_schema import make_graph, to_jsonable
import json

g = make_graph()
mine_github_issues(g)
data = to_jsonable(g)
patch = {"nodes": data["nodes"], "edges": data["edges"]}
with open("github_patch.json", "w") as f:
    json.dump(patch, f, indent=2)
