
from __future__ import annotations
import pandas as pd
import numpy as np

ALIASES = {
    "date": ["date","sale_date","sales_date","transaction_date","order_date","datetime"],
    "product": ["product","product_name","item","item_name","sku","product_id"],
    "quantity": ["quantity","qty","units_sold","sales_quantity","sales_qty","units"],
    "inventory": ["inventory","stock","current_stock","stock_quantity","available_stock"],
    "category": ["category","product_category","department","segment"],
    "brand": ["brand","brand_name","manufacturer_brand"],
    "company": ["company","company_name","manufacturer","vendor_company"],
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    out.columns=[str(c).strip().lower().replace(" ","_").replace("-","_") for c in out.columns]
    return out

def detect_columns(df: pd.DataFrame):
    normalized={str(c).strip().lower().replace(" ","_").replace("-","_"): c for c in df.columns}
    mapping={}
    confidence={}
    for target, aliases in ALIASES.items():
        found=None
        for alias in aliases:
            if alias in normalized:
                found=normalized[alias]; break
        mapping[target]=found
        confidence[target]=1.0 if found else 0.0
    return mapping, confidence

def score_quality(df: pd.DataFrame, mapping: dict):
    n=max(len(df),1)
    completeness=100.0*float(df.notna().mean().mean()) if len(df.columns) else 0
    duplicate_pct=100.0*(1-len(df.drop_duplicates())/n)
    validity=100.0
    consistency=100.0
    issues=[]

    date_col=mapping.get("date")
    qty_col=mapping.get("quantity")
    product_col=mapping.get("product")

    if date_col:
        parsed=pd.to_datetime(df[date_col],errors="coerce")
        invalid=int(parsed.isna().sum())
        if invalid:
            issues.append(f"{invalid} invalid date records")
        validity-=min(40,invalid/n*100)
    else:
        validity=0
        issues.append("Date column is missing")

    if qty_col:
        nums=pd.to_numeric(df[qty_col],errors="coerce")
        invalid=int(nums.isna().sum())
        negative=int((nums.dropna()<0).sum())
        if invalid:
            issues.append(f"{invalid} invalid quantity records")
        if negative:
            issues.append(f"{negative} negative quantity records")
        validity-=min(40,invalid/n*100)
        validity-=min(20,negative/n*100)
    else:
        validity=0
        issues.append("Quantity column is missing")

    if not product_col:
        consistency=0
        issues.append("Product column is missing")

    duplicate_score=max(0,100-duplicate_pct)
    score=round(0.30*completeness+0.30*validity+0.25*consistency+0.15*duplicate_score)
    return {
        "score":score,
        "completeness":round(completeness,2),
        "validity":round(max(0,validity),2),
        "consistency":round(consistency,2),
        "duplicates":round(duplicate_score,2),
        "duplicate_rows":int(df.duplicated().sum()),
        "issues":issues
    }

def clean_dataframe(df: pd.DataFrame, mapping: dict):
    out=normalize_columns(df)
    # mapping must be re-detected after normalization
    mapping,_=detect_columns(out)

    if mapping["date"]:
        out["_date"]=pd.to_datetime(out[mapping["date"]],errors="coerce")
    if mapping["quantity"]:
        out["_quantity"]=pd.to_numeric(out[mapping["quantity"]],errors="coerce")
    if mapping["product"]:
        out["_product"]=out[mapping["product"]].astype(str).str.strip()

    before=len(out)
    out=out.drop_duplicates().copy()
    duplicate_removed=before-len(out)

    if "_date" in out:
        out=out[out["_date"].notna()].copy()
    if "_quantity" in out:
        out=out[out["_quantity"].notna() & (out["_quantity"]>=0)].copy()
    if "_product" in out:
        out=out[out["_product"].notna() & (out["_product"].str.len()>0)].copy()

    if "_date" in out:
        out["_date"]=out["_date"].dt.normalize()

    return out, duplicate_removed

def forecast_readiness(df: pd.DataFrame, mapping: dict):
    checks=[]
    date_ok=bool(mapping.get("date"))
    product_ok=bool(mapping.get("product"))
    qty_ok=bool(mapping.get("quantity"))
    checks.append(("Historical Records",len(df)>0))
    checks.append(("Date Field",date_ok))
    checks.append(("Product Mapping",product_ok))
    checks.append(("Quantity Field",qty_ok))

    enough=False
    if date_ok and product_ok and qty_ok:
        dates=pd.to_datetime(df[mapping["date"]],errors="coerce").dropna()
        if len(dates):
            span=(dates.max()-dates.min()).days
            enough=span>=45
    checks.append(("Sufficient History",enough))
    ready=all(x[1] for x in checks)
    return {"ready":ready,"checks":[{"name":n,"passed":bool(v)} for n,v in checks],
            "message":"READY FOR FORECASTING" if ready else "More valid historical data is required before forecasting."}
