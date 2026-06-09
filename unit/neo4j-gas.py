from py2neo import Graph
import pandas as pd
import math
import re
from unit.path import Args


def valid(v):
    return (
        v is not None
        and not (isinstance(v, float) and math.isnan(v))
        and str(v).strip() != ""
    )


def split_vals(v):
    if not valid(v):
        return []
    return [x.strip() for x in str(v).split(",")]


def parse_numeric(val):
    if not valid(val):
        return None

    s = str(val)
    # 2.23 × 10-6
    m = re.search(r'([+-]?\d*\.?\d+)\s*[×x*]\s*10-?([+-]?\d+)', s)
    if m:
        return float(m.group(1)) * (10 ** (-int(m.group(2))))
    # 2.23 × 10^6
    m = re.search(r'([+-]?\d*\.?\d+)\s*[×x*]\s*10\^([+-]?\d+)', s)
    if m:
        return float(m.group(1)) * (10 ** int(m.group(2)))
    # scientific notation
    m = re.search(r'([+-]?\d*\.?\d+[eE][+-]?\d+)', s)
    if m:
        return float(m.group(1))
    m = re.search(r'([+-]?\d*\.?\d+)', s)
    return float(m.group(1)) if m else None


def extract_unit(value_str):
    if not valid(value_str):
        return None
    s = str(value_str)
    m = re.search(r'[0-9\.\-\+\s×x\*\^Ee]+(.*)', s)
    if m:
        unit = m.group(1).strip()
        return unit if unit else None
    return None


class KGBuilder:

    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        self.clear()

    def clear(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("Neo4j database cleared")

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

        # ------------------Material------------------
        self.graph.run("""
            MERGE (mat:Material {name:$name})
            SET mat.filler_ratio=$ratio
        """, name=final_material, ratio=ratio)

        # ------------------Operation------------------
        create_operation = temperature is not None or pressure is not None
        operation_name = None
        if create_operation:
            parts = []
            if temperature is not None:
                parts.append(f"{temperature}K")
            if pressure is not None:
                parts.append(f"{pressure}bar")
            operation_name = "_".join(parts)
            self.graph.run("""
                MERGE (op:Operation {name:$name})
                SET op.temperature=$temp,
                    op.pressure=$pres
            """, name=operation_name, temp=temperature, pres=pressure)
            self.graph.run("""
                MATCH (mat:Material {name:$mat})
                MATCH (op:Operation {name:$op})
                MERGE (mat)-[:OPERATED_UNDER]->(op)
            """, mat=final_material, op=operation_name)

        # ------------------Permea*------------------
        gases = split_vals(row.get("Gas"))
        permeas = split_vals(row.get("Permea*"))
        for gas, permea in zip(gases, permeas):
            self.graph.run("""
                MERGE (g:Gas {name:$gas})
                WITH g
                MATCH (mat:Material {name:$mat})
                MERGE (g)-[:TESTED_ON]->(mat)
            """, gas=gas, mat=final_material)

            node_data = {
                "gas": gas,
                "value_str": permea,
                "value": parse_numeric(permea),
                "unit": extract_unit(permea)
            }

            if create_operation:
                self.graph.run("""
                    MATCH (op:Operation {name:$op})
                    CREATE (p:`Permea*` {
                        gas:$gas,
                        value_str:$value_str,
                        value:$value,
                        unit:$unit
                    })
                    MERGE (op)-[:HAS_PERMEA]->(p)
                """, op=operation_name, **node_data)
            else:
                self.graph.run("""
                    MATCH (mat:Material {name:$mat})
                    CREATE (p:`Permea*` {
                        gas:$gas,
                        value_str:$value_str,
                        value:$value,
                        unit:$unit
                    })
                    MERGE (mat)-[:HAS_PERMEA]->(p)
                """, mat=final_material, **node_data)

        # ------------------Selectivity------------------
        mixtures = split_vals(row.get("Mixture"))
        sels = split_vals(row.get("Selectivity"))
        for mix, sel in zip(mixtures, sels):
            self.graph.run("""
                MERGE (g:Gas {name:$gas})
                WITH g
                MATCH (mat:Material {name:$mat})
                MERGE (g)-[:TESTED_ON]->(mat)
            """, gas=mix, mat=final_material)

            node_data = {
                "gas": mix,
                "value_str": sel,
                "value": parse_numeric(sel)
            }

            if create_operation:
                self.graph.run("""
                    MATCH (op:Operation {name:$op})
                    CREATE (p:Selectivity {
                        gas:$gas,
                        value_str:$value_str,
                        value:$value
                    })
                    MERGE (op)-[:HAS_SELECTIVITY]->(p)
                """, op=operation_name, **node_data)
            else:
                self.graph.run("""
                    MATCH (mat:Material {name:$mat})
                    CREATE (p:Selectivity {
                        gas:$gas,
                        value_str:$value_str,
                        value:$value
                    })
                    MERGE (mat)-[:HAS_SELECTIVITY]->(p)
                """, mat=final_material, **node_data)

    def insert_all(self, df):
        for i, row in df.iterrows():
            self.insert_row(row, i)
        print("Knowledge Graph construction completed")


if __name__ == "__main__":
    gas_path = Args().gas
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "your_password"

    df = pd.read_excel(gas_path)
    kg = KGBuilder(URI, USER, PASSWORD)
    kg.insert_all(df)
