# Why the pixel-area bound changed in spec 2

The job specifies A = R² (sin north − sin south) (east − west in radians).
For 0.05-degree pixels, writing the width as `deg2rad(0.05)`, subtracting
longitude edges before conversion, or subtracting their converted radians are
equivalent real-arithmetic calculations. At longitudes near 38 degrees, the
edge subtraction loses relative precision compared with the small pixel width.

Both initial agent submissions used the stated edge formula. Their maximum
area difference from the reference was 2.0042061805725098e-6 m². Every rainfall
array, coordinate and coarse-cell assignment agreed. Spec 1's declared bound
was 3.552713678800514e-7 m², so both answers became unresolved. This was a
grader defect. Independent reference implementations had both simplified the
width to 0.05 and did not expose it.

The shared tolerance rule is 2 gamma_n M, with gamma_n = n u / (1 − n u),
u = 2^-53. Spec 1 incorrectly used only the final area magnitude (<5e7 m²).
For the parenthesized formula, R² = 40,589,641,000,000 is an exact integer below
2^53. Multiplying it by either angular span can produce an intermediate up to
4e10 before the second small angular factor reduces it to the final area.
The supplied latitude range and 0.05-degree width bound each span below 0.001
radian. Other intermediate coordinates/angles/trigonometric values are smaller.
The operation allowance is 32, including edge construction, angle conversion,
trigonometric rounding and final arithmetic. This assumes ordinary float64
sin implementations accurate to approximately one ulp on these small angles.

Spec 2 therefore uses **n=32, M=4e10**, giving approximately **2.8422e-4 m²**.
This is an input/intermediate error bound, not a tolerance fitted to observed
agent errors. It remains below 1e-11 relative to a pixel area. A one-metre radius
error changes the area by about 9.7 m² and is decisively rejected. Rainfall
tolerances, exact geometry labels and all scientific rules are unchanged.

A new known-correct control uses edge subtraction throughout its calculations.
A regression compares equivalent area formulas and rejects a wrong radius.
Original spec-1 assessments remain unchanged. Both frozen submissions are
reassessed separately under spec 2, without another agent attempt. Reports keep
submission and assessment versions separate. No historical pass rate is pooled
across these contracts.
