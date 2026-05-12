from py2neo import Graph
import pandas as pd
import math
import re
from unit.path import Args


def valid(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() != ""


def split_vals(v):
    if not valid(v):
        return []
    return [x.strip() for x in str(v).split(",")]


def is_mixture(name):
    return "/" in name


def parse_numeric(val):
    if not valid(val):
        return None

    s = str(val)

    m = re.search(r'([+-]?\d*\.?\d+)\s*[×x*]\s*10\^?([+-]?\d+)', s)
    if m:
        return float(m.group(1)) * 10 ** int(m.group(2))

    m = re.search(r'([+-]?\d*\.?\d+[eE][+-]?\d+)', s)
    if m:
        return float(m.group(1))

    m = re.search(r'([+-]?\d*\.?\d+)', s)
    return float(m.group(1)) if m else None


class KGBuilder:

    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        self.clear()
        # self.create_indexes()

    def clear(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("Neo4j database cleared")

    def create_indexes(self):
        self.graph.run("CREATE INDEX IF NOT EXISTS FOR (g:Gas) ON (g.name)")
        self.graph.run("CREATE INDEX IF NOT EXISTS FOR (m:Mixture) ON (m.name)")
        self.graph.run("CREATE INDEX IF NOT EXISTS FOR (m:Membrane) ON (m.name)")
        self.graph.run("CREATE INDEX IF NOT EXISTS FOR (m:Material) ON (m.name)")
        self.graph.run("CREATE INDEX IF NOT EXISTS FOR (f:Filler) ON (f.name)")
        print("Indexes created")

    def insert_row(self, row, row_index):

        material_name = row.get("Membrane Material")
        filler_name = row.get("Fill Name")
        filler_ratio = row.get("Fill Ratio")

        temperature = parse_numeric(row.get("Temperature"))
        pressure = parse_numeric(row.get("Pressure"))

        if valid(filler_name):
            final_material = filler_name
            ratio = filler_ratio
        elif valid(material_name):
            final_material = material_name
            ratio = None
        else:
            return

        self.graph.run("""
            MERGE (mat:Material {name:$name})
            SET mat.filler_ratio = $ratio
        """, name=final_material, ratio=ratio)

        create_operation = (temperature is not None) or (pressure is not None)

        if create_operation:

            parts = []
            if temperature is not None:
                parts.append(f"{temperature}K")
            if pressure is not None:
                parts.append(f"{pressure}bar")

            operation_name = "_".join(parts)

            self.graph.run("""
                MERGE (op:Operation {name:$name})
                SET op.temperature = $temp,
                    op.pressure = $pres
            """, name=operation_name,
                           temp=temperature,
                           pres=pressure)

            self.graph.run("""
                MATCH (mat:Material {name:$mat})
                MATCH (op:Operation {name:$op})
                MERGE (mat)-[:OPERATED_UNDER]->(op)
            """, mat=final_material,
                           op=operation_name)

        gases = split_vals(row.get("Gas"))
        permeas = split_vals(row.get("Permea*"))

        mixtures = split_vals(row.get("Mixture"))
        sels = split_vals(row.get("Selectivity"))

        # ----------Single Gas----------
        for gas, p in zip(gases, permeas):

            self.graph.run("""
                MERGE (g:Gas {name:$gas})
                WITH g
                MATCH (mat:Material {name:$mat})
                MERGE (g)-[:TESTED_ON]->(mat)
            """, gas=gas, mat=final_material)

            if create_operation:
                self.graph.run("""
                    MATCH (op:Operation {name:$op})
                    CREATE (perf:Performance {
                        gas:$gas,
                        permeability_str:$p_str,
                        permeability:$p_val
                    })
                    MERGE (op)-[:HAS_PERFORMANCE]->(perf)
                """,
                               op=operation_name,
                               gas=gas,
                               p_str=p,
                               p_val=parse_numeric(p))
            else:
                self.graph.run("""
                    MATCH (mat:Material {name:$mat})
                    CREATE (perf:Performance {
                        gas:$gas,
                        permeability_str:$p_str,
                        permeability:$p_val
                    })
                    MERGE (mat)-[:HAS_PERFORMANCE]->(perf)
                """,
                               mat=final_material,
                               gas=gas,
                               p_str=p,
                               p_val=parse_numeric(p))

        # ----------Gas Mixture----------
        for mix, sel in zip(mixtures, sels):

            self.graph.run("""
                MERGE (g:Gas {name:$gas})
                WITH g
                MATCH (mat:Material {name:$mat})
                MERGE (g)-[:TESTED_ON]->(mat)
            """, gas=mix, mat=final_material)

            if create_operation:
                self.graph.run("""
                    MATCH (op:Operation {name:$op})
                    CREATE (perf:Performance {
                        gas:$gas,
                        selectivity_str:$sel_str,
                        selectivity:$sel_val
                    })
                    MERGE (op)-[:HAS_PERFORMANCE]->(perf)
                """,
                               op=operation_name,
                               gas=mix,
                               sel_str=sel,
                               sel_val=parse_numeric(sel))
            else:
                self.graph.run("""
                    MATCH (mat:Material {name:$mat})
                    CREATE (perf:Performance {
                        gas:$gas,
                        selectivity_str:$sel_str,
                        selectivity:$sel_val
                    })
                    MERGE (mat)-[:HAS_PERFORMANCE]->(perf)
                """,
                               mat=final_material,
                               gas=mix,
                               sel_str=sel,
                               sel_val=parse_numeric(sel))

    # Batch insertion
    def insert_all(self, df):
        for i, row in df.iterrows():
            self.insert_row(row, i)
        print("Knowledge Graph construction completed")


if __name__ == "__main__":

    gas_path = Args().gas
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "your_password"
    EXCEL_PATH = gas_path
    df = pd.read_excel(EXCEL_PATH)

    kg = KGBuilder(URI, USER, PASSWORD)
    kg.insert_all(df)