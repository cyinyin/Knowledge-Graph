# Knowledge Graph: Construction of Different Membrane Separation Systems

## Requirements

- Python(>=3)
    
Python modules（version used in this work）    

- pandas (2.0.3)
- py2neo (2021.2.4)
- neo4j (5.28.2)
 
## Project structure
```bash
root
|-- data        
|   |--gas.xlsx        // Membrane gas separation data
|   |--liquid.xlsx        // Membrane liquid separation data   
|-- unit // Building a knowledge graph
|   |-- neo4j-gas.py     // Building a knowledge graph for gas separation
|   |-- neo4j-liquid.py  //  Building a knowledge graph for liquid separation
|   |-- path.py  // Pathway 
```
## Usage：
1、Download Neo4j 

    https://neo4j.com/deployment-center/#community;

2、Start Neo4j

    Windows: Double-click neo4j-community-2025.10.1-windows\bin\neo4j.bat
    macOS/Linux: ./bin/neo4j console
3、Verify the port

    Bolt: localhost:7687
    HTTP: localhost:7474 
    Default username: neo4j
    Default password: Set a password

4、Build a knowledge graph
    
    Run the corresponding code for the separation system
