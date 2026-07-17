# Reading Data into a DataFrame

This example demonstrates how to load a Harp register's binary data file into a
pandas DataFrame using `harp.data`. The register definition tells `parse_to_dataframe`
how to decode each frame, so you get named columns (and decoded enums) for free.

<!--codeinclude-->
```python
[](./read_data_to_dataframe.py)
```
<!--/codeinclude-->
