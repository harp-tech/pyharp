# Reading Data into a DataFrame

This example demonstrates how to load a **single** Harp register's binary data
file into a pandas DataFrame using `harp.data`. The register definition tells
`parse_to_dataframe` how to decode each frame, so you get named columns (and
decoded enums) for free.

!!! tip
    Have a whole recorded session folder rather than one loose file? Use
    [`DatasetReader`](../read_dataset/read_dataset.md), which reads every register
    in a dataset folder driven by the device schema.

<!--codeinclude-->
```python
[](./read_data_to_dataframe.py)
```
<!--/codeinclude-->
