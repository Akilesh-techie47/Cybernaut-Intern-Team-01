# AeroDelay AI Dataset Audit Report

**Source:** US DOT BTS On-Time Performance - Reporting Carrier  
**Inspection Date:** 2026-11-03T13:59:59.666830+00:00  
**Files Inspected:** 1  

## Minimum Requirements Check

- **Usable Records:** 526,882 (minimum required: 500)
  - ✅ PASS  
- **Meaningful Predictors:** 7 (minimum required: 6)
  - ✅ PASS  

## Target Distribution

- **0.00**: 385163
- **1.00**: 141719
- **nan**: 30213

## Identified Predictors (7)

1. **Reporting_Airline**
2. **Origin**
3. **Dest**
4. **Month**
5. **Distance**
6. **Cancelled**
7. **Diverted**

## Potential Leakage Columns (0)

None observed.

## Missing-Value Summary

- **Tail_Number**: 7897 total missing (1.42%)
- **Deptime**: 30203 total missing (5.42%)
- **Depdelay**: 30213 total missing (5.42%)
- **Depdelayminutes**: 30213 total missing (5.42%)
- **Depdel15**: 30213 total missing (5.42%)
- **Departuredelaygroups**: 30213 total missing (5.42%)
- **Taxiout**: 30464 total missing (5.47%)
- **Wheelsoff**: 30464 total missing (5.47%)
- **Wheelson**: 30832 total missing (5.53%)
- **Taxiin**: 30832 total missing (5.53%)
- **Arrtime**: 30832 total missing (5.53%)
- **Arrdelay**: 31880 total missing (5.72%)
- **Arrdelayminutes**: 31880 total missing (5.72%)
- **Arrdel15**: 31880 total missing (5.72%)
- **Arrivaldelaygroups**: 31880 total missing (5.72%)
- **Cancellationcode**: 526513 total missing (94.51%)
- **Actualelapsedtime**: 31880 total missing (5.72%)
- **Airtime**: 31880 total missing (5.72%)
- **Carrierdelay**: 414688 total missing (74.44%)
- **Weatherdelay**: 414688 total missing (74.44%)
- **Nasdelay**: 414688 total missing (74.44%)
- **Securitydelay**: 414688 total missing (74.44%)
- **Lateaircraftdelay**: 414688 total missing (74.44%)
- **Firstdeptime**: 553558 total missing (99.37%)
- **Totaladdgtime**: 553557 total missing (99.36%)
- **Longestaddgtime**: 553557 total missing (99.36%)
- **Divairportlandings**: 1 total missing (0.0%)
- **Divreacheddest**: 555798 total missing (99.77%)
- **Divactualelapsedtime**: 556047 total missing (99.81%)
- **Divarrdelay**: 556048 total missing (99.81%)
- **Divdistance**: 555798 total missing (99.77%)
- **Div1Airport**: 555679 total missing (99.75%)
- **Div1Airportid**: 555679 total missing (99.75%)
- **Div1Airportseqid**: 555679 total missing (99.75%)
- **Div1Wheelson**: 555679 total missing (99.75%)
- **Div1Totalgtime**: 555679 total missing (99.75%)
- **Div1Longestgtime**: 555679 total missing (99.75%)
- **Div1Wheelsoff**: 556038 total missing (99.81%)
- **Div1Tailnum**: 556038 total missing (99.81%)
- **Div2Airport**: 557077 total missing (100.0%)
- **Div2Airportid**: 557077 total missing (100.0%)
- **Div2Airportseqid**: 557077 total missing (100.0%)
- **Div2Wheelson**: 557077 total missing (100.0%)
- **Div2Totalgtime**: 557077 total missing (100.0%)
- **Div2Longestgtime**: 557077 total missing (100.0%)
- **Div2Wheelsoff**: 557086 total missing (100.0%)
- **Div2Tailnum**: 557086 total missing (100.0%)
- **Div3Airport**: 557095 total missing (100.0%)
- **Div3Airportid**: 557095 total missing (100.0%)
- **Div3Airportseqid**: 557095 total missing (100.0%)
- **Div3Wheelson**: 557095 total missing (100.0%)
- **Div3Totalgtime**: 557095 total missing (100.0%)
- **Div3Longestgtime**: 557095 total missing (100.0%)
- **Div3Wheelsoff**: 557095 total missing (100.0%)
- **Div3Tailnum**: 557095 total missing (100.0%)
- **Div4Airport**: 557095 total missing (100.0%)
- **Div4Airportid**: 557095 total missing (100.0%)
- **Div4Airportseqid**: 557095 total missing (100.0%)
- **Div4Wheelson**: 557095 total missing (100.0%)
- **Div4Totalgtime**: 557095 total missing (100.0%)
- **Div4Longestgtime**: 557095 total missing (100.0%)
- **Div4Wheelsoff**: 557095 total missing (100.0%)
- **Div4Tailnum**: 557095 total missing (100.0%)
- **Div5Airport**: 557095 total missing (100.0%)
- **Div5Airportid**: 557095 total missing (100.0%)
- **Div5Airportseqid**: 557095 total missing (100.0%)
- **Div5Wheelson**: 557095 total missing (100.0%)
- **Div5Totalgtime**: 557095 total missing (100.0%)
- **Div5Longestgtime**: 557095 total missing (100.0%)
- **Div5Wheelsoff**: 557095 total missing (100.0%)
- **Div5Tailnum**: 557095 total missing (100.0%)
- **Unnamed: 109**: 557095 total missing (100.0%)

## Duplicate Rows

- **Total duplicate rows:** 0

## Warnings

- No warnings.

## Errors

- No errors.
