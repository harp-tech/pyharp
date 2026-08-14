# Reading Data into a DataFrame

This example demonstrates how to load the binary data file of a **single** Harp register into a pandas DataFrame using `harp.data`. The register definition tells `parse_to_dataframe` how to decode each frame, so the result carries named columns and decoded enums.

!!! tip
    For a whole recorded session folder rather than one loose file, use [`DatasetReader`](../read_dataset/read_dataset.md), which reads every register in a dataset folder based on the device schema.

<!--codeinclude-->
```python
[](./read_data_to_dataframe.py)
```
<!--/codeinclude-->
