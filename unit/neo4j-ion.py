from py2neo import Graph
import pandas as pd
import math
import re
from unit.path import Args


def valid(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() not in ["", "-", "--", "nan", "NaN"]


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    v = str(v).strip()
    if v.lower() in ["", "-", "--", "nan", "none"]:
        return None
    return v


def split_multi(v):
    if not valid(v):
        return []
    return [i.strip() for i in str(v).replace(";", ",").split(",") if i.strip()]


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


class IonKG:

    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        self.clear()

    def clear(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("Neo4j database cleared")

    def insert_row(self, row):

        materials = clean(row.get("Membrane_Materials"))
        fillers = clean(row.get("Fillers"))
        ratio = clean(row.get("Fill_Ratio"))

        system = clean(row.get("Separation_System"))
        component = clean(row.get("Separation_Component"))
        tech = clean(row.get("Separation_Technology"))

        temp = parse_numeric(row.get("Temperature"))
        press = parse_numeric(row.get("Pressure"))
        ph = clean(row.get("pH"))
        conc = clean(row.get("Concentration"))

        permeance = clean(row.get("Permeance"))
        flux = clean(row.get("Flux"))
        selectivity = clean(row.get("Selectivity"))

        if valid(fillers):
            mat_list = split_multi(fillers)
        elif valid(materials):
            mat_list = split_multi(materials)
        else:
            return

        material_name = "+".join(mat_list)

        self.graph.run("""
        MERGE (m:Material {name:$name})
        SET m.fill_ratio = $ratio
        """, name=material_name, ratio=ratio)

        if valid(system):
            self.graph.run("""
            MERGE (s:System {name:$name})
            """, name=system)

            self.graph.run("""
            MATCH (m:Material {name:$mat})
            MATCH (s:System {name:$sys})
            MERGE (m)-[:USED_IN]->(s)
            """, mat=material_name, sys=system)

        if valid(component):
            for c in split_multi(component):
                self.graph.run("""
                MERGE (c:Component {name:$name})
                """, name=c)

                self.graph.run("""
                MATCH (s:System {name:$sys})
                MATCH (c:Component {name:$c})
                MERGE (s)-[:SEPARATES]->(c)
                """, sys=system, c=c)

        if valid(tech):
            self.graph.run("""
            MERGE (t:Technology {name:$name})
            """, name=tech)

            self.graph.run("""
            MATCH (m:Material {name:$mat})
            MATCH (t:Technology {name:$tech})
            MERGE (m)-[:APPLIED_TECH]->(t)
            """, mat=material_name, tech=tech)

        if any([temp, press, ph, conc]):

            op_name = "_".join([
                str(temp) if temp else "",
                str(press) if press else ""
            ]).strip("_")

            self.graph.run("""
            MERGE (o:Operation {name:$name})
            SET o.temperature=$temp,
                o.pressure=$press,
                o.ph=$ph,
                o.concentration=$conc
            """, name=op_name,
                   temp=temp, press=press, ph=ph, conc=conc)

            self.graph.run("""
            MATCH (m:Material {name:$mat})
            MATCH (o:Operation {name:$op})
            MERGE (m)-[:OPERATED_UNDER]->(o)
            """, mat=material_name, op=op_name)

        def add_perf(label, value, rel):
            if valid(value):
                for v in split_multi(value):
                    self.graph.run(f"""
                    MERGE (p:{label} {{value:$val}})
                    """, val=v)

                    self.graph.run(f"""
                    MATCH (m:Material {{name:$mat}})
                    MATCH (p:{label} {{value:$val}})
                    MERGE (m)-[:HAS_{rel}]->(p)
                    """, mat=material_name, val=v)

        add_perf("Permeance", permeance, "PERMEANCE")
        add_perf("Flux", flux, "FLUX")
        add_perf("Selectivity", selectivity, "SELECTIVITY")

    def insert_all(self, df):
        for _, row in df.iterrows():
            self.insert_row(row)
        print("Knowledge Graph construction completed")


if __name__ == "__main__":

    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "your_password"

    df = pd.read_excel(Args().ion)

    kg = IonKG(URI, USER, PASSWORD)
    kg.insert_all(df)