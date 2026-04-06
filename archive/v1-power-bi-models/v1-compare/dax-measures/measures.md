# DAX Measures — Xer_Compare_two_projects

## Metrics.Task_Count
```dax
CALCULATE(counta(TASK[task_id]))
```

## Metrics.Budget Labor Units
```dax
CALCULATE(sum(TASK[target_work_qty]),TASK[target_work_qty]<>0)
```

## Metrics.Actual Start
```dax
CALCULATE(min(TASK[act_start_date]))
```

## Metrics.Start_Date
```dax
CALCULATE(min(TASK[Start]))
```

## Metrics.Actual Labor Untis
```dax
CALCULATE(sum(TASK[act_work_qty]))
```

## Metrics.Finish_Date
```dax
CALCULATE(max(TASK[Finish]))
```

## Metrics.Remaining Labor Unit
```dax
calculate(sum(TASK[remain_work_qty]),TASK[remain_work_qty]<>0)
```

## Metrics.At Completion Labor Units
```dax
[Actual Labor Untis]+[Remaining Labor Unit]
```

## Metrics.Sort
```dax
if([Task_Count]=BLANK(),BLANK(),CALCULATE(max(PROJWBS[Master_Sort])))
```

## Metrics.Actual Finish
```dax
CALCULATE(mAX(TASK[act_end_date]))
```

## Metrics.Task_Count_Negative_Float
```dax
CALCULATE(counta(TASK[task_id]),TASK[total_float_hr_cnt]<0)
```

## Metrics.Task_Count_Float_0
```dax
CALCULATE(counta(TASK[task_id]),filter(task,TASK[status_code]<>"TK_Complete"&&TASK[total_float_hr_cnt]=0))
```

## Metrics.Task_Count_Completed
```dax
CALCULATE(counta(TASK[task_id]),TASK[status_code]="TK_Complete")
```

## Metrics.Primary Constraints
```dax
CALCULATE(counta(TASK[task_id]),TASK[cstr_type]<>BLANK())
```

## Metrics.Task_Count_Ongoing
```dax
CALCULATE(counta(TASK[task_id]),TASK[status_code]="TK_active")
```

## Metrics.Task_Count_Not_Started
```dax
CALCULATE(counta(TASK[task_id]),TASK[status_code]="TK_Notstart")
```

## Metrics.LOE
```dax
CALCULATE(counta(TASK[task_id]),TASK[task_type]="TT_LOE")
```

## Metrics.Finish Milestone
```dax
CALCULATE(counta(TASK[task_id]),TASK[task_type]="TT_finmile")
```

## Metrics.Start Milestone
```dax
CALCULATE(counta(TASK[task_id]),TASK[task_type]="TT_mile")
```

## Metrics.Task Dependent
```dax
CALCULATE(counta(TASK[task_id]),TASK[task_type]="TT_task")
```

## Metrics.Count_Task_Duration_%
```dax
CALCULATE(counta(TASK[task_id]),TASK[complete_pct_type]="cp_drtn")
```

## Metrics.Count_Task_Units_%
```dax
CALCULATE(counta(TASK[task_id]),TASK[complete_pct_type]="cp_units")
```

## Metrics.Count_Task_Phys_%
```dax
CALCULATE(counta(TASK[task_id]),TASK[complete_pct_type]="cp_phys")
```

## Metrics.Missing Predecessor
```dax
if(CALCULATE(sum(TASK[Predecessor]))=0,BLANK(),CALCULATE(sum(TASK[Predecessor])))
```

## Metrics.Budget Non Labor Units
```dax
CALCULATE(sum(TASK[target_equip_qty]),TASK[target_equip_qty]<>0)
```

## Metrics.Actual Non Labor Units
```dax
CALCULATE(sum(TASK[act_equip_qty]))
```

## Metrics.Remaining Non Labor Unit
```dax
CALCULATE(sum(TASK[remain_equip_qty]))
```

## Metrics.At Completion Non Labor Units
```dax
[Actual Non Labor Units]+[Remaining Non Labor Unit]
```

## Metrics.Task_Counts_Not_Completed
```dax
[Task_Count_Not_Started]+[Task_Count_Ongoing]
```

## Metrics.%_Labor_units
```dax
DIVIDE([Actual Labor Untis],[At Completion Labor Units],BLANK())
```

## Metrics.Total_Float
```dax
CALCULATE(min(TASK[Total_Float]))
```

## Metrics.Active
```dax
CALCULATE(COUNTROWS(task), 
    FILTER(task, ([Start] <= LASTDATE(Mstdate[Date]) 
        && [finish]>= FIRSTDATE(Mstdate[Date]))))
```

## PROJWBS.Master_sort_
```dax
min(PROJWBS[Master_Sort])&FORMAT([Finish_Date],"yymmdd")
```

## Metrics.Activity status
```dax
FIRSTNONBLANK(TASK[Activity status],TASK[Activity status]<>BLANK())
```

## Metrics.Project_1_Total_Float
```dax
CALCULATE([Total_Float],filter(PROJECT,PROJECT[Index]=1))
```

## Metrics.Project_2_Total_Float
```dax
CALCULATE([Total_Float],filter(PROJECT,PROJECT[Index]=2))
```

## Metrics.Project_1_Activities
```dax
CALCULATE(SELECTEDVALUE(TASK[task_name]),filter(PROJECT,PROJECT[Index]=1))
```

## Metrics.Project_2_Activities
```dax
CALCULATE(SELECTEDVALUE(TASK[task_name]),filter(PROJECT,PROJECT[Index]=2))
```

## Metrics.Change_Description
```dax
if([Project_1_Activities]=[Project_2_Activities],"No","Yes")
```

## Metrics.Total_Float_Erosion
```dax
if(or([Project_2_Total_Float]=BLANK(),[Project_1_Total_Float]=BLANK()),BLANK(),[Project_2_Total_Float]-[Project_1_Total_Float])
```

