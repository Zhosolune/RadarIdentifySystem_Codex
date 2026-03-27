import torch
import os

def convert_to_onnx(model_path, output_path, input_shape, device='cpu'):
    """
    将 TorchScript (.pt) 模型转换为 ONNX 格式。
    
    Args:
        model_path (str): .pt 模型文件的路径
        output_path (str): 输出 .onnx 文件的路径
        input_shape (tuple): 模型输入的形状 (Batch, Channel, Height, Width)
        device (str): 运行设备 ('cpu' 或 'cuda')
    """
    print(f"正在处理: {os.path.basename(model_path)}")
    
    if not os.path.exists(model_path):
        print(f"错误: 找不到文件 {model_path}")
        return False

    try:
        # 加载模型
        print("  正在加载模型...")
        model = torch.jit.load(model_path, map_location=device)
        model.eval() # 切换到评估模式

        # 创建虚拟输入
        print(f"  创建虚拟输入: {input_shape}")
        dummy_input = torch.randn(input_shape, device=device)

        # 导出为 ONNX
        print(f"  正在导出到 {output_path} ...")
        try:
            torch.onnx.export(
                model,
                dummy_input,
                output_path,
                verbose=False,
                input_names=['input'],
                output_names=['output'],
                opset_version=12,
                do_constant_folding=True,
                export_params=True,
                dynamo=False 
            )
        except TypeError:
             print("  重试：使用标准导出...")
             torch.onnx.export(
                model,
                dummy_input,
                output_path,
                verbose=False,
                input_names=['input'],
                output_names=['output'],
                opset_version=12,
                do_constant_folding=True
            )
            
        print(f"成功! 已保存至: {output_path}")
        return True
        
    except Exception as e:
        print(f"转换失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # 获取脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # =================== 配置 ===================
    
    # 1. DTOA 模型
    # 文件名
    dtoa_pt_name = "01.28_ResNet_Base_DTOA-final-29-accuracy98.55-val_accuracy98.75.pt"
    dtoa_onnx_name = "01.28_ResNet_Base_DTOA-final-29-accuracy98.55-val_accuracy98.75.onnx"
    # 输入尺寸 (Batch=1, Channel=1, Height=250, Width=500)
    dtoa_shape = (1, 1, 250, 500)

    # 2. PA 模型
    # 文件名
    pa_pt_name = "01.28_ResNetWide_PA-checkpoint-45-accuracy0.99-val_accuracy0.99.pt"
    pa_onnx_name = "01.28_ResNetWide_PA-checkpoint-45-accuracy0.99-val_accuracy0.99.onnx"
    # 输入尺寸 (Batch=1, Channel=1, Height=80, Width=400)
    pa_shape = (1, 1, 80, 400)

    # ===========================================

    # 构建完整路径
    dtoa_pt_path = os.path.join(current_dir, dtoa_pt_name)
    dtoa_onnx_path = os.path.join(current_dir, dtoa_onnx_name)

    pa_pt_path = os.path.join(current_dir, pa_pt_name)
    pa_onnx_path = os.path.join(current_dir, pa_onnx_name)

    # 执行转换
    success_count = 0
    total_count = 2

    print("=== 开始转换模型 ===")
    
    # 转换 DTOA
    if convert_to_onnx(dtoa_pt_path, dtoa_onnx_path, dtoa_shape):
        success_count += 1
        
    # 转换 PA
    if convert_to_onnx(pa_pt_path, pa_onnx_path, pa_shape):
        success_count += 1

    print(f"=== 转换完成: {success_count}/{total_count} 成功 ===")

if __name__ == "__main__":
    main()
