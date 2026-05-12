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

    def clean_val(self, v):

        if v is None:
            return None

        if pd.isna(v):
            return None

        v = str(v).strip()

        if v in ["", "-", "--", "nan", "NaN"]:
            return None

        return v

    def valid(self, v):

        return self.clean_val(v) is not None

    def split_vals(self, v):

        v = self.clean_val(v)

        if v is None:
            return []

        return [i.strip() for i in str(v).split(";") if i.strip()]

    def insert_row(self, row, idx):

        component = self.clean_val(row.get("Separation_Component"))

        material = self.clean_val(row.get("Membrane_Materials"))
        filler = self.clean_val(row.get("Fillers"))

        if self.valid(filler):
            final_material = filler
        else:
            final_material = material

        if not self.valid(final_material):
            return

        temp = self.clean_val(row.get("Temperature"))
        press = self.clean_val(row.get("Pressure"))
        ph = self.clean_val(row.get("pH"))
        conc = self.clean_val(row.get("Concentration"))

        permeances = self.split_vals(row.get("Permeance"))
        fluxes = self.split_vals(row.get("Flux"))
        sels = self.split_vals(row.get("Selectivity"))

        self.graph.run("""
        MERGE (m:Material {name:$name})
        """, name=final_material)

        create_operation = any([
            self.valid(temp),
            self.valid(press),
            self.valid(ph),
            self.valid(conc)
        ])

        if create_operation:
            self.graph.run("""
            CREATE (o:Operation)
            SET o.temperature=$temp,
                o.pressure=$press,
                o.ph=$ph,
                o.concentration=$conc
            """,
                           temp=temp,
                           press=press,
                           ph=ph,
                           conc=conc)

            self.graph.run("""
            MATCH (m:Material {name:$mat})
            MATCH (o:Operation {
                temperature:$temp,
                pressure:$press,
                ph:$ph,
                concentration:$conc
            })
            MERGE (m)-[:OPERATED_UNDER]->(o)
            """,
                           mat=final_material,
                           temp=temp,
                           press=press,
                           ph=ph,
                           conc=conc)

        for permeance in permeances:

            self.graph.run("""
            CREATE (p:Permeance {value:$val})
            """, val=permeance)

            if create_operation:

                self.graph.run("""
                MATCH (o:Operation {
                    temperature:$temp,
                    pressure:$press,
                    ph:$ph,
                    concentration:$conc
                })
                MATCH (p:Permeance {value:$val})
                MERGE (o)-[:HAS_PERMEANCE]->(p)
                """,
                               temp=temp,
                               press=press,
                               ph=ph,
                               conc=conc,
                               val=permeance)

            else:

                self.graph.run("""
                MATCH (m:Material {name:$mat})
                MATCH (p:Permeance {value:$val})
                MERGE (m)-[:HAS_PERMEANCE]->(p)
                """,
                               mat=final_material,
                               val=permeance)

        for flux in fluxes:

            self.graph.run("""
            CREATE (f:Flux {value:$val})
            """, val=flux)

            if create_operation:

                self.graph.run("""
                MATCH (o:Operation {
                    temperature:$temp,
                    pressure:$press,
                    ph:$ph,
                    concentration:$conc
                })
                MATCH (f:Flux {value:$val})
                MERGE (o)-[:HAS_FLUX]->(f)
                """,
                               temp=temp,
                               press=press,
                               ph=ph,
                               conc=conc,
                               val=flux)

            else:

                self.graph.run("""
                MATCH (m:Material {name:$mat})
                MATCH (f:Flux {value:$val})
                MERGE (m)-[:HAS_FLUX]->(f)
                """,
                               mat=final_material,
                               val=flux)

        for sel in sels:

            self.graph.run("""
            CREATE (s:Selectivity {value:$val})
            """, val=sel)

            if create_operation:

                self.graph.run("""
                MATCH (o:Operation {
                    temperature:$temp,
                    pressure:$press,
                    ph:$ph,
                    concentration:$conc
                })
                MATCH (s:Selectivity {value:$val})
                MERGE (o)-[:HAS_SELECTIVITY]->(s)
                """,
                               temp=temp,
                               press=press,
                               ph=ph,
                               conc=conc,
                               val=sel)

            else:

                self.graph.run("""
                MATCH (m:Material {name:$mat})
                MATCH (s:Selectivity {value:$val})
                MERGE (m)-[:HAS_SELECTIVITY]->(s)
                """,
                               mat=final_material,
                               val=sel)

        if self.valid(component):
            self.graph.run("""
            MERGE (c:Component {name:$comp})
            """, comp=component)

            self.graph.run("""
            MATCH (c:Component {name:$comp})
            MATCH (m:Material {name:$mat})
            MERGE (c)-[:SEPARATED_BY]->(m)
            """,
                           comp=component,
                           mat=final_material)

    def insert_all(self, df):
        for i, row in df.iterrows():
            self.insert_row(row, i)
        print("Knowledge Graph construction completed")


if __name__ == "__main__":
    liquid_path = Args().liquid
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "your_password"
    EXCEL_PATH = liquid_path
    df = pd.read_excel(EXCEL_PATH)

    kg = KGBuilder(URI, USER, PASSWORD)
    kg.insert_all(df)