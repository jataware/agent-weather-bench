# Conventions for this task

These are the conventions the task expects. Each is a statement about the data or about what the brief means.

- **Rainfall is accumulated.** `tp` is the rainfall accumulated since the forecast started, in kg m⁻², which equals mm. The rain that falls between two times is the later value minus the earlier value.
- **Small decreases.** The accumulation sometimes decreases slightly from one day to the next. Set those daily amounts to zero, or keep them. Record which under `choices`.
- **A 7-day period.** The period beginning on date D runs from D 00:00 UTC to D+7 days 00:00 UTC. Its total is the accumulation at D+7 days minus the accumulation at D.
- **Same calendar dates.** Compare the two issues over the same calendar dates. The earlier issue reaches those dates at a longer lead time.
- **Cells on the edge.** A grid cell is inside the rectangle when its centre lies inside or exactly on an edge.
- **Regional mean.** Weight each cell by the cosine of its latitude.
