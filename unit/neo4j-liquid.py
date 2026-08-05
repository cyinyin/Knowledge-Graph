from py2neo import Graph
import pandas as pd
import math
from unit.path import Args


class KGBuilder:

    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        self.clear()

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

    def clear(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("Neo4j database cleared")

    def insert_row(self, row, idx):

        component = self.clean_val(row.get("Separation_Component"))

        if component and component.lower() == "water":
            return

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

        transport_perf = self.clean_val(row.get("Transport performance"))
        transport_metric = self.clean_val(row.get("Transport metric"))

        sels = self.split_vals(row.get("Selectivity"))

        self.graph.run("""
            MERGE (m:Material {name:$name})
        """, name=final_material)

        create_operation = any([self.valid(temp), self.valid(press), self.valid(ph), self.valid(conc)])

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

        if self.valid(transport_metric) and self.valid(transport_perf):
            metric_lower = transport_metric.lower()
            if metric_lower == "permeance":
                label = "Permeance"
            elif metric_lower == "flux":
                label = "Flux"
            else:
                label = None  

            if label:
                perf_vals = self.split_vals(transport_perf)
                for perf_val in perf_vals:
                    self.graph.run(f"""
                    CREATE (p:{label} {{value:$val}})
                    """, val=perf_val)

                    if create_operation:
                        self.graph.run(f"""
                        MATCH (o:Operation {{
                            temperature:$temp,
                            pressure:$press,
                            ph:$ph,
                            concentration:$conc
                        }})
                        MATCH (p:{label} {{value:$val}})
                        MERGE (o)-[:HAS_{label.upper()}]->(p)
                        """,
                                       temp=temp,
                                       press=press,
                                       ph=ph,
                                       conc=conc,
                                       val=perf_val)
                    else:
                        self.graph.run(f"""
                        MATCH (m:Material {{name:$mat}})
                        MATCH (p:{label} {{value:$val}})
                        MERGE (m)-[:HAS_{label.upper()}]->(p)
                        """,
                                       mat=final_material,
                                       val=perf_val)
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

        if component:
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
