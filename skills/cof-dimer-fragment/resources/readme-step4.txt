## 说明：第四步
## 需要文件：上一步优化后的得到的所有cif文件：放在opted_cifs/下面
4-1： 运行：step4-1-cut_dimer_from_cif.ipynb，将所有文件切出，得到所有的mol文件
得到：cuted_mols/

##需要文件：要计算的数据集的统计结果。这里是：训练+迁移-0129.txt  
4-2：运行：step4-2-choose_dimers_in_data.ipynb得到最终要计算的dimer对应的xyz文件：XXX_addH.xyz
